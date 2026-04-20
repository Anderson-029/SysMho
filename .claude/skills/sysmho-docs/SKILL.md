---
name: sysmho-docs
description: Generates and audits professional documentation following Diátaxis, ADR (Michael Nygard), Keep-a-Changelog, Google Python Style, OpenAPI 3.0, and C4 Model standards.
allowed-tools: Read, Bash, Write, Glob, Grep
---

# sysmho-docs — Documentación Profesional SysMho

Genera y audita la documentación del proyecto aplicando **estándares reales del mundo laboral**.
No inventa formatos — sigue normas usadas en Google, Amazon, HashiCorp, Django, ING, Spotify.

---

## Estándares Aplicados

| Estándar | Origen | Aplica a |
|----------|--------|----------|
| **Diátaxis** | Daniele Procida / Django, Ubuntu, Cloudflare | Organización general de docs |
| **ADR** | Michael Nygard / ThoughtWorks, Amazon, HashiCorp | Decisiones arquitectónicas |
| **Keep a Changelog** | keepachangelog.com / estándar OSS global | CHANGELOG.md |
| **Google Python Style** | google.github.io/styleguide/pyguide | Docstrings en código Python |
| **OpenAPI 3.0** | OpenAPI Initiative (Linux Foundation) | Endpoints REST API |
| **C4 Model** | Simon Brown / Spotify, ING Bank | Diagramas de arquitectura |
| **RFC-style** | IETF / Google, Stripe (internamente) | Specs técnicas del sistema |

---

## Paso 1 — Diátaxis Audit (Clasificación de Documentación)

Diátaxis divide la documentación en 4 cuadrantes según propósito:

| Cuadrante | Pregunta que responde | Ejemplo en SysMho |
|-----------|----------------------|-------------------|
| **Tutorial** | "¿Cómo aprendo?" (orientado a aprendizaje) | Cómo hacer tu primer deploy de SysMho |
| **How-to** | "¿Cómo hago X?" (orientado a tareas) | Cómo reentrenar el modelo, cómo configurar CB |
| **Reference** | "¿Qué es X?" (orientado a información) | AGENTS.md, docstrings, API endpoints |
| **Explanation** | "¿Por qué funciona así?" (orientado a comprensión) | ADRs, decisiones de arquitectura |

**Audit:**
```bash
# Listar toda la documentación existente
find . -name "*.md" -not -path "./.git/*" | sort

# Clasificar en cuadrantes (leer contenido y asignar):
# - CLAUDE.md → Reference + Explanation
# - AGENTS.md → Reference
# - skills/*.md → How-to
# - ADRs (si existen) → Explanation
# - README.md → Tutorial + Reference
```

**Reportar gaps:** ¿Qué cuadrantes faltan? Typical gap en SysMho: Tutorial (no hay guía de onboarding paso a paso).

---

## Paso 2 — ADR Generation (Architecture Decision Records)

**Formato estándar Michael Nygard** (usado en ThoughtWorks Tech Radar, Amazon, HashiCorp Vault):

```markdown
# ADR-NNN: Título de la Decisión

**Date:** YYYY-MM-DD
**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXX
**Deciders:** Anderson

## Context
¿Qué situación o problema forzó tomar esta decisión?
¿Qué restricciones o fuerzas estaban en juego?

## Decision
¿Qué se decidió hacer?

## Consequences
### Positivas
- ...
### Negativas / Trade-offs
- ...
### Deuda Técnica Generada
- ...
```

**ADRs a generar desde CLAUDE.md y architecture.md:**

```bash
# Leer decisiones documentadas
Read CLAUDE.md
Read .claude/rules/architecture.md
```

ADRs identificados para SysMho:
- `ADR-001-xgboost-over-neural-networks.md` — Por qué XGBoost vs redes neuronales para trading
- `ADR-002-ollama-local-as-primary-llm.md` — Ollama local vs cloud-only (privacidad + costo)
- `ADR-003-sliding-window-3-months.md` — Ventana de entrenamiento 3 meses vs histórico completo
- `ADR-004-asyncpg-sqlalchemy2.md` — Async-first DB vs ORM síncrono
- `ADR-005-jwt-stateless-auth.md` — JWT Bearer vs sessions (CSRF, SPAs)
- `ADR-006-circuit-breaker-pattern.md` — CB pattern para proteger capital en drawdown

**Crear directorio y archivos:**
```bash
mkdir -p docs/adr
# Generar cada ADR con el formato estándar arriba
Write docs/adr/ADR-001-xgboost-over-neural-networks.md
Write docs/adr/ADR-002-ollama-local-as-primary-llm.md
# etc.
```

---

## Paso 3 — Changelog (Keep a Changelog v1.0.0)

**Estándar:** keepachangelog.com — usado por millones de proyectos OSS.
**Principios:** Legible por humanos, agrupado por versión semver, categorías fijas.

**Formato:**
```markdown
# Changelog
All notable changes to SysMho are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

## [Unreleased]

## [15.2.0] - 2026-04-04
### Added
- Gap Filler automático al arranque
- PnL diario en dashboard
- Docker-first deployment

### Changed
- XGBoost v3 con 28 features (symbol_encoded + contexto macro)

### Fixed
- Race condition en monitor
- Side detection bug

## [15.0.0] - 2026-03-XX
### Added
- Modo autónomo con MetaEvaluator
- Circuit Breaker automático
- SelfLearner (actualización post-trade)
```

**Generar desde git log:**
```bash
git log --oneline --decorate | head -50
git tag --sort=-version:refname | head -20
# Agrupar commits por versión y clasificar en categorías
Write docs/CHANGELOG.md
```

---

## Paso 4 — Docstring Audit (Google Python Style Guide)

**Estándar Google:** https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings

**Formato correcto:**
```python
def predict_signal(self, symbol: str, df: pd.DataFrame) -> dict:
    """Predicts trading signal using XGBoost model.

    Applies the trained model to compute class probabilities,
    then filters via inertia and strength-ratio guards.

    Args:
        symbol: Trading pair (e.g. 'BTC/USDT').
        df: DataFrame with 27 features, last row is current candle.

    Returns:
        dict with keys:
            - signal (str): 'BUY', 'SELL', or 'WAIT'
            - confidence (float): Dominant class probability [0,1]
            - meta (dict): Raw probabilities and filter results

    Raises:
        ValueError: If df has fewer than 27 feature columns.
        ModelNotLoadedError: If model file is missing.

    Example:
        >>> predictor = ModelPredictor()
        >>> result = predictor.predict_signal('BTC/USDT', features_df)
        >>> result['signal']
        'BUY'
    """
```

**Auditar módulos críticos:**
```bash
# Buscar funciones/clases sin docstrings en módulos críticos
Grep "def " src/ai/predictor.py      # predictor principal
Grep "def " src/ai/trainer.py        # trainer
Grep "def " src/ai/meta_evaluator.py # meta evaluador
Grep "def " src/ai/self_learner.py   # self learner
Grep "def " src/analysis/features.py # feature engineering
Grep "def " src/executor/trader.py   # ejecutor de trades

# Para cada función: verificar si tiene docstring en la línea siguiente
# Generar reporte: funciones auditadas vs funciones con docstring
```

**Output:** Reporte `docs/DOC_HEALTH_REPORT.md` con % de cobertura de docstrings.

---

## Paso 5 — OpenAPI 3.0 API Reference

**Estándar:** OpenAPI Initiative (Linux Foundation) — base de Swagger UI, Postman, etc.

FastAPI genera OpenAPI automáticamente en `/docs`. Complementar con referencia markdown:

```bash
# Listar todos los endpoints del dashboard
Glob src/dashboard/routes/*.py
Read src/dashboard/api.py
# Para cada router: extraer endpoints, métodos, parámetros, auth

# Verificar OpenAPI en vivo (si dashboard corre):
# curl http://localhost:8000/openapi.json
```

**Formato para docs/API_REFERENCE.md:**
```markdown
# SysMho API Reference
Base URL: http://localhost:8000
Authentication: Bearer JWT (Authorization: Bearer <token>)

## Authentication
### POST /auth/login
Login with username and password.

**Request:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| username | string | ✅ | Admin username |
| password | string | ✅ | Admin password |

**Response 200:**
```json
{"access_token": "...", "refresh_token": "...", "expires_in": 1800}
```

**Errors:** 401 Invalid credentials, 429 Rate limited (5 req/min)

---
## Signals
### GET /api/v1/signals/pending
...
```

```bash
Write docs/API_REFERENCE.md
```

---

## Paso 6 — C4 Model (Arquitectura)

**Estándar C4:** Simon Brown — usado en Spotify, ING Bank, muchas fintech.
4 niveles de zoom: Context → Container → Component → Code.

**Level 1 — System Context (quién usa SysMho y con qué interactúa):**
```
┌─────────────────────────────────────────────────────────┐
│                    SYSTEM CONTEXT                        │
│                                                         │
│  [Anderson] ──uses──> [SysMho] ──trades──> [Binance]    │
│                          │                              │
│                          ├──inference──> [Ollama Local] │
│                          ├──fallback──>  [Gemini Cloud]  │
│                          └──stores──>    [PostgreSQL]    │
└─────────────────────────────────────────────────────────┘
```

**Level 2 — Container (los procesos/apps dentro de SysMho):**
```
┌─────────────────────────────────────────────────────────┐
│                    CONTAINERS                            │
│                                                         │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │  AI Engine   │    │  Dashboard   │                   │
│  │  (src/main)  │    │  (FastAPI)   │◄─── Browser       │
│  │  port: -     │    │  port: 8000  │                   │
│  └──────┬───────┘    └──────┬───────┘                   │
│         │                  │                            │
│         └────────┬─────────┘                            │
│                  │                                      │
│         ┌────────▼────────┐                             │
│         │   PostgreSQL    │                             │
│         │   port: 5432    │                             │
│         └─────────────────┘                             │
└─────────────────────────────────────────────────────────┘
```

**Generar en Mermaid (renderizable en GitHub):**
```bash
# Construir diagrama desde AGENTS.md + src/AGENTS.md
Read src/AGENTS.md
Read AGENTS.md
Write docs/ARCHITECTURE.md  # Con bloques ```mermaid```
```

---

## Paso 7 — RFC-style Technical Specification

**Formato inspirado en IETF RFC + Google internal TDD (Technical Design Doc):**
Usado en Google, Stripe, Airbnb para documentar sistemas complejos.

**Archivo:** `docs/specs/SPEC-001-ml-prediction-pipeline.md`

```markdown
# SPEC-001: ML Prediction Pipeline

| Field | Value |
|-------|-------|
| Status | Active |
| Version | v3 (28 features) |
| Last Updated | 2026-04-20 |
| Owner | Anderson |

## 1. Motivation
Why this pipeline exists and what problem it solves.

## 2. Goals
- Classify candle direction (BUY/SELL/WAIT) with >85% accuracy
- Latency <10ms per prediction (Level 1 ML)
- Adaptive to market regime changes (sliding window retrain)

## 3. Non-Goals
- Real-time tick-level predictions
- Multi-exchange arbitrage

## 4. Design
### 4.1 Data Flow
Binance WebSocket → market_data (PostgreSQL)
  → FeatureEngineer.get_master_dataframe() [27 features]
  → ModelPredictor.predict_signal() [XGBoost predict_proba]
  → Inertia filter (WAIT > 72% → veto)
  → Strength ratio (dom/opp ≥ 2.0)
  → MetaEvaluator [meta_score ≥ 0.52]
  → TradeExecutor / pending_approvals

### 4.2 Feature Set (28 features)
[Lista completa desde src/constants.py MODEL_FEATURES]

### 4.3 Model Architecture
- Algorithm: XGBoost (gradient boosted trees)
- Training: Sliding window 3 months, TimeSeriesSplit 5 folds
- Classes: 0=SELL, 1=WAIT, 2=BUY
- Label threshold: 0.7% price movement

## 5. Alternatives Considered
- LSTM/Transformer: Higher latency, overfits on small datasets
- Random Forest: Lower accuracy, no probability calibration
- Rule-based: No adaptation to market regimes

## 6. Known Limitations
- Model degrades after major market structure changes
- Sliding window may miss long-term patterns (>3 months)
- funding_rate data availability varies by symbol

## 7. Operational Notes
- Retrain: uv run python -m src.ai.trainer --symbol ALL --timeframe 5m
- Monitor accuracy: /sysmho-metrics
- Model guard: src/constants.py MODEL_FEATURES changes require retrain
```

```bash
mkdir -p docs/specs
Write docs/specs/SPEC-001-ml-prediction-pipeline.md
```

---

## Paso 8 — Documentation Health Report

Genera `docs/DOC_HEALTH_REPORT.md` con métricas de estado de la documentación:

```bash
# 1. Contar funciones totales vs funciones con docstrings en módulos críticos
MODULES=(
  "src/ai/predictor.py"
  "src/ai/trainer.py"
  "src/ai/meta_evaluator.py"
  "src/ai/self_learner.py"
  "src/analysis/features.py"
  "src/executor/trader.py"
  "src/collector/gap_filler.py"
  "src/database/repository.py"
)

# Para cada módulo:
# total_funcs = grep -c "def " file
# funcs_with_docstring = grep -A1 "def " file | grep -c '"""'
# coverage = funcs_with_docstring / total_funcs * 100

# 2. Verificar cuadrantes Diátaxis cubiertos
# 3. Listar ADRs existentes vs ADRs identificados
# 4. Verificar que CHANGELOG.md existe y tiene entradas recientes
# 5. Calcular días desde última actualización de docs
```

**Formato del reporte:**
```markdown
# Documentation Health Report
Generated: YYYY-MM-DD

## Overall Score: X/100

## Diátaxis Coverage
- [x] Reference (AGENTS.md, docstrings)
- [x] Explanation (ADRs)
- [ ] How-to (skills parciales — faltan N guías)
- [ ] Tutorial (sin guía de onboarding)

## Docstring Coverage (Google Style)
| Module | Functions | With Docstring | Coverage |
|--------|-----------|----------------|----------|
| predictor.py | 8 | 3 | 37.5% |
| trainer.py | 5 | 2 | 40.0% |
...
| **TOTAL** | **47** | **18** | **38.3%** |

## ADRs
- Documented: 6 ADRs
- Pending (identified, not written): 2

## Changelog
- Last entry: v15.2.0 (2026-04-04) — 16 days ago

## Recommendations (Priority Order)
1. 🔴 Write Tutorial: "Deploying SysMho from scratch"
2. 🟡 Add docstrings to predictor.py (3 functions missing)
3. 🟡 Write ADR-007 for Circuit Breaker parameters
4. 🟢 Update CHANGELOG with current work
```

---

## Output Final

```
docs/
├── adr/
│   ├── ADR-001-xgboost-over-neural-networks.md
│   ├── ADR-002-ollama-local-as-primary-llm.md
│   ├── ADR-003-sliding-window-3-months.md
│   ├── ADR-004-asyncpg-sqlalchemy2.md
│   ├── ADR-005-jwt-stateless-auth.md
│   └── ADR-006-circuit-breaker-pattern.md
├── specs/
│   └── SPEC-001-ml-prediction-pipeline.md
├── CHANGELOG.md
├── API_REFERENCE.md
├── ARCHITECTURE.md
└── DOC_HEALTH_REPORT.md
```

Después de ejecutar esta skill:
1. Revisa `docs/DOC_HEALTH_REPORT.md` para ver gaps prioritarios
2. Usa el score de docstrings como baseline para mejora continua
3. Los ADRs son el input para onboarding de nuevos colaboradores
