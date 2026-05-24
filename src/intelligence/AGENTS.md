# AGENTS.md — src/intelligence/ Module

> **Navigation:** `CLAUDE.md` → `src/AGENTS.md` → This file
>
> **When to read:** Understanding how Gemini Intelligence investigates market context and integrates with MetaEvaluador
> **Module responsibility:** Web-based market investigation, context report generation, persistent storage

---

## Module Overview

The **Gemini Intelligence Layer** investigates crypto market context every 5-minute trading cycle using Google Gemini 2.0 Flash with web search. Results are stored persistently in PostgreSQL and consumed by MetaEvaluador as the 6th scoring component.

**Key insight**: XGBoost (28 features) predicts technical moves. Gemini investigates *why* — macro context, news, whale activity, sentiment. Orthogonal components = better decisions.

---

## Entry Point

```python
# src/main.py
async def _gemini_intelligence_loop(self):
    """
    Runs every 5-minute cycle.
    
    Timeline:
      0s:00   → Cycle starts
      3:45    → Triggers get_context_report()
      4:30    → Report saved to DB and cached in self.last_gemini_context
      5:00    → Cycle end
    
    Timeout: 45 seconds (hard limit)
    Fallback: Returns neutral report if Gemini unavailable, times out, or fails parsing
    """
```

**Called from**: `src/main.py:run()` — spawned as async task alongside other 8 loops.

---

## GeminiIntelligenceAgent — Class API

File: `src/intelligence/gemini_agent.py`

### Constructor

```python
def __init__(self) -> None:
    api_key = os.getenv('GEMINI_API_KEY', '')
    self._enabled = bool(api_key)
    if self._enabled:
        self._client = genai.Client(api_key=api_key)
    self._min_interval = int(os.getenv('GEMINI_MIN_REINVESTIGATE_INTERVAL', 
                                       GEMINI_MIN_REINVESTIGATE))
```

- Reads `GEMINI_API_KEY` from `.env`
- Initializes Google genai Client if key is present
- Sets re-investigation minimum interval (default 1800s = 30 min)
- If disabled, returns neutral reports (zero regression risk)

### Main Method: `get_context_report()`

```python
async def get_context_report(
    self,
    last_report: Optional[dict],
    hour_utc: int,
    db_context: Optional[str] = None,
) -> dict:
    """
    Entry point for MetaEvaluador.
    
    Logic:
      1. If not enabled → return neutral report
      2. If last_report exists AND elapsed < min_interval → reuse (increment reuse_count)
      3. Otherwise → call Gemini with timeout(45s), parse response, save to DB
    
    Args:
        last_report: Previous investigation result (or None)
        hour_utc: Current UTC hour (for "optimal_hour" determination)
        db_context: System state context (daily trades, PnL, balance)
    
    Returns:
        {
            'sentiment_score': float -1.0 to +1.0,
            'whale_pressure': int -1 | 0 | 1,
            'macro_bias': int -1 | 0 | 1,
            'news_risk_level': int 0 | 1 | 2,
            'optimal_hour': bool,
            'llm_veto': bool (emergency stop),
            'significant_changes': dict,
            'sources_checked': list[str],
            'gemini_reasoning': str (one-liner),
            'was_reinvestigated': bool,
            'reuse_count': int,
            'full_report': dict,
            '_timestamp': float (Unix time),
        }
    """
```

### Internal Methods

#### `_should_reinvestigate(last_report: Optional[dict]) -> bool`

```python
def _should_reinvestigate(self, last_report: Optional[dict]) -> bool:
    """
    Avoids excessive API calls by skipping re-investigation if:
      - last_report exists
      - elapsed time < GEMINI_MIN_REINVESTIGATE (default 1800s)
    
    Cost savings: With 3 hours of trading per day, saves ~2-3 Gemini API calls/day.
    """
```

#### `_run_investigation(hour_utc: int, db_context: str) -> dict`

```python
async def _run_investigation(self, hour_utc: int, db_context: str) -> dict:
    """
    1. Constructs prompt with system symbols and current hour
    2. Calls self._client.models.generate_content() with GoogleSearch tool
    3. Timeout: 45 seconds (asyncio.wait_for)
    4. Parses JSON response
    5. Returns dict or neutral fallback if parsing fails
    
    Prompt investigates:
      - News (CoinDesk, Cointelegraph, CryptoPanic) — last 2 hours
      - Whale activity (whale-alert.io) — recent large transfers
      - Sentiment (Fear & Greed Index, CoinGecko trending)
      - Macro (BTC.D, DXY, liquidations, funding rates)
    
    All sources are public and free (no paywalls).
    """
```

#### `_parse_response(raw: str) -> dict`

```python
def _parse_response(self, raw: str) -> dict:
    """
    Handles variations in Gemini output:
      - Raw JSON
      - JSON wrapped in markdown code fences
      - JSON starting with ```json
    
    Normalizes all values to valid ranges:
      - sentiment_score: clamp to [-1.0, 1.0]
      - whale_pressure: clamp to [-1, 1]
      - macro_bias: clamp to [-1, 1]
      - news_risk_level: clamp to [0, 2]
    
    If JSON parsing fails → returns neutral report (never crashes)
    """
```

---

## Database Integration

Table: `gemini_market_context` (created by `migration_v15_3_0.sql`)

```sql
CREATE TABLE gemini_market_context (
    id                  SERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    sentiment_score     NUMERIC(4,3),           -- -1.000 to +1.000
    whale_pressure      SMALLINT,               -- -1 | 0 | 1
    macro_bias          SMALLINT,               -- -1 | 0 | 1
    news_risk_level     SMALLINT,               -- 0 | 1 | 2
    optimal_hour        BOOLEAN,
    llm_veto            BOOLEAN DEFAULT FALSE,
    significant_changes JSONB,
    sources_checked     TEXT[],
    full_report         JSONB,
    gemini_reasoning    TEXT,
    was_reinvestigated  BOOLEAN,
    reuse_count         SMALLINT,
    version             TEXT
);
```

**Queries** (via `src/database/repository.py`):

```python
async def save_gemini_context(self, report: dict) -> None:
    """Insert report into gemini_market_context"""

async def get_latest_gemini_context(self) -> Optional[dict]:
    """Fetch most recent report, deserialize JSONB fields, return as dict"""
```

---

## Integration with MetaEvaluador (Component 6)

File: `src/ai/meta_evaluator.py`

```python
def evaluate(
    self,
    signal: dict,
    recent_trades: Optional[List[dict]] = None,
    window_penalty: float = 0.0,
    gemini_context: Optional[dict] = None,  # ← NEW PARAMETER
) -> Tuple[float, bool, List[str]]:
```

**Scoring logic**:

1. **Immediate veto**: If `gemini_context.llm_veto == True` and `GEMINI_VETO_BLOCKS_TRADE == True`:
   - Returns `(0.0, False, ["🚫 Gemini VETO: ..."])`
   - Zero discussion — trade blocked regardless of XGBoost confidence

2. **6-component meta_score** (if no veto):
   - Normalize 4 Gemini fields to [0..1]:
     ```
     sentiment_norm = (sentiment + 1) / 2        # -1→0.0, 0→0.5, +1→1.0
     whale_norm     = (whale + 1) / 2
     macro_norm     = (macro + 1) / 2
     news_norm      = 1 - (news_risk / 2)        # 0→1.0, 1→0.5, 2→0.0
     hour_score     = 0.60 if optimal_hour else 0.40
     
     gemini_score = sentiment_norm * 0.30
                  + whale_norm     * 0.25
                  + macro_norm     * 0.25
                  + news_norm      * 0.10
                  + hour_score     * 0.10
     ```

   - Add to `score_components` list (6th component)
   - `meta_score = mean(score_components)` (now includes Gemini)

3. **Backward compatibility**: If `gemini_context=None`:
   - Falls back to 5-component scoring (no breaking change)
   - System still works without Gemini API key

---

## Constants

File: `src/constants.py`

```python
GEMINI_START_OFFSET_SECONDS = 225      # Minute 3:45 of 5m cycle
GEMINI_MAX_WAIT_SECONDS     = 45       # Timeout for Gemini response
GEMINI_MODEL                = 'gemini-2.0-flash'
GEMINI_MIN_REINVESTIGATE    = 1800     # 30 min between re-investigations
GEMINI_VETO_BLOCKS_TRADE    = True     # If True, llm_veto overrides XGBoost
```

**Customization**:
- Override in `.env`: `GEMINI_MIN_REINVESTIGATE_INTERVAL=3600` (1 hour instead of 30 min)
- Override `GEMINI_VETO_BLOCKS_TRADE` in `.env` if you want Gemini as advisory only

---

## Configuration & Secrets

File: `.env` (never committed)

```bash
# Required for Gemini Intelligence
GEMINI_API_KEY=<your_google_gemini_api_key>
GEMINI_MIN_REINVESTIGATE_INTERVAL=1800  # seconds between re-investigations

# Optional — override defaults
# GEMINI_MODEL=gemini-2.0-flash  (already default)
# CB_GEMINI_VETO_BLOCKS_TRADE=false  (enable advisory-only mode)
```

**How to get GEMINI_API_KEY**:
1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create new API key (free tier: unlimited with rate limits)
3. Paste into `.env`

---

## Sources Investigated

All **public, free** sources (no paywalls, no authentication):

| Source | Data | URL Pattern |
|--------|------|------------|
| CryptoPanic | News aggregator (200+ sources) | cryptopanic.com |
| CoinDesk | Tier-1 crypto news | coindesk.com |
| Cointelegraph | Tier-1 crypto news | cointelegraph.com |
| Decrypt | Crypto news | decrypt.com |
| Whale Alert | Large on-chain transfers | whale-alert.io |
| Fear & Greed Index | Market sentiment | alternative.me/fng |
| CoinGecko | Trending coins, market data | coingecko.com |
| CoinGlass | Liquidations, funding rates | coinglass.com |

---

## Fallback & Error Handling

**Three fallback layers**:

1. **API key missing**: Returns neutral report (no crash)
2. **Gemini timeout (>45s)**: Catches `asyncio.TimeoutError`, returns neutral report
3. **JSON parse error**: Catches Exception, returns neutral report

**Neutral report** (`_NEUTRAL_REPORT`):
```python
{
    'sentiment_score': 0.0,
    'whale_pressure': 0,
    'macro_bias': 0,
    'news_risk_level': 0,
    'optimal_hour': True,
    'llm_veto': False,
    'significant_changes': {},
    'sources_checked': [],
    'gemini_reasoning': 'Fallback neutral — Gemini no disponible',
    'was_reinvestigated': False,
    'reuse_count': 0,
}
```

**Zero regression**: If Gemini is unavailable, system operates on 5-component MetaEvaluador scores (same as v15.2.0).

---

## Monitoring

**Logs** (from `src/main.py`):
```
[GEMINI] Investigating market context at 3:45...
[GEMINI] Report: sentiment=+0.25 whale=SELL macro=NEUTRAL news=LOW
[GEMINI] Reusing previous report (reuse_count=3)
[GEMINI] Investigation timed out — falling back to neutral
[GEMINI] Parsing failed — falling back to neutral
```

**Database** (query recent reports):
```sql
SELECT created_at, sentiment_score, whale_pressure, macro_bias, 
       llm_veto, was_reinvestigated
FROM gemini_market_context
ORDER BY created_at DESC
LIMIT 10;
```

---

## Performance Profile

| Metric | Value | Notes |
|--------|-------|-------|
| API calls per hour | ~1 | Re-investigates every 30 min (saves costs) |
| Timeout | 45s | Hard limit to fit within 5-min cycle |
| DB writes per day | ~2-4 | Only when reinvestigation happens |
| Token cost | $0-2/month | Gemini free tier has rate limits |

---

## Testing & Validation

Covered by existing test suite:
- `test_phase1.py`: Version consistency, imports, constants
- `test_phase3.py`: Integration tests (via `/sysmho` skill)

Manual validation:
```bash
# 1. Check GeminiIntelligenceAgent initializes
uv run python -c "from src.intelligence import GeminiIntelligenceAgent; print('✅')"

# 2. Run engine and monitor logs
uv run engine 2>&1 | grep -i gemini

# 3. Query DB for recent reports
uv run python -c "
import asyncio
from src.database.repository import DatabaseRepository
from config.settings import settings

async def check():
    db = DatabaseRepository(settings.database_url)
    ctx = await db.get_latest_gemini_context()
    print(f'Latest report: {ctx}')

asyncio.run(check())
"
```

---

## Related Documentation

- `src/ai/AGENTS.md` — MetaEvaluador (6-component scoring)
- `src/database/AGENTS.md` — `gemini_market_context` table schema
- `src/AGENTS.md` — Module dependencies diagram
- `CLAUDE.md` — System manifest, critical rules
