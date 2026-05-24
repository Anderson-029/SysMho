"""
SysMho — Gemini Intelligence Agent.

Investiga el contexto de mercado cada 5 minutos (a partir del minuto 3:45)
usando Gemini con acceso web completo. Genera un ContextReport estructurado
que el MetaEvaluador usa como componente adicional en la toma de decisiones.

Fuentes consultadas (todas públicas, sin costo):
  - CryptoPanic.com       (noticias agregadas de 200+ fuentes)
  - CoinDesk.com          (noticias Tier-1)
  - Cointelegraph.com     (noticias Tier-1)
  - Decrypt.com           (noticias)
  - whale-alert.io        (movimientos de ballenas)
  - alternative.me/fng    (Fear & Greed Index)
  - coingecko.com         (trending y datos de mercado)
  - coinglass.com         (liquidaciones y futuros)
  - tradingview.com       (BTC.D, DXY, macro)
  - investing.com         (macro global)

Flujo:
  1. Al minuto 3:45 del ciclo, el orquestador llama a get_context_report()
  2. Si no hay reporte previo o el mercado cambió → investiga con Gemini
  3. Si el reporte es reciente y sin cambios → reutiliza (ahorra API calls)
  4. Devuelve siempre un ContextReport válido (fallback neutral si Gemini falla)
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

from google import genai
from google.genai import types

from src.constants import (
    GEMINI_MODEL,
    GEMINI_MIN_REINVESTIGATE,
    SYMBOLS,
)


_NEUTRAL_REPORT = {
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
    'full_report': {},
}

_INVESTIGATION_PROMPT = """
Eres un analista de mercado crypto experto. Haz una investigación RÁPIDA y PRECISA
del estado actual del mercado para ayudar a un sistema de trading algorítmico a
tomar mejores decisiones en los próximos 5 minutos.

Portafolio activo: {symbols}
Hora UTC actual: {hour_utc}:00

INVESTIGA ESTAS FUENTES (en este orden de prioridad):

1. NOTICIAS (últimas 2 horas):
   - cryptopanic.com (busca las noticias más recientes)
   - coindesk.com
   - cointelegraph.com
   Busca: ¿Hay noticias que puedan mover el mercado? ¿Regulaciones, hacks, listings?

2. MOVIMIENTOS BALLENA:
   - whale-alert.io (busca transacciones grandes recientes)
   Busca: ¿Hubo movimientos de +1000 BTC o equivalente? ¿A exchange o cold wallet?

3. SENTIMIENTO:
   - alternative.me/fng (Fear & Greed Index actual)
   - coingecko.com/en/discover (trending coins)
   Busca: ¿Cuál es el índice hoy? ¿Qué activos están trending?

4. MACRO Y LIQUIDACIONES:
   - coinglass.com (liquidaciones recientes totales)
   - tradingview.com (busca BTC.D y DXY actuales)
   Busca: ¿Hay liquidaciones masivas? ¿El dólar se fortaleció o debilitó?

CONTEXTO PROPIO DEL SISTEMA:
{db_context}

RESPONDE ÚNICAMENTE EN ESTE JSON EXACTO (sin texto adicional):
{{
    "sentiment_score": <float entre -1.0 y 1.0>,
    "whale_pressure": <-1 (presión SELL) | 0 (neutral) | 1 (presión BUY)>,
    "macro_bias": <-1 (bearish) | 0 (neutral) | 1 (bullish)>,
    "news_risk_level": <0 (sin riesgo) | 1 (riesgo medio) | 2 (riesgo alto)>,
    "optimal_hour": <true si es buena hora para operar, false si no>,
    "llm_veto": <true SOLO si hay noticia/evento que justifique pausar trading>,
    "significant_changes": {{
        "news": <true/false>,
        "whales": <true/false>,
        "macro": <true/false>,
        "sentiment": <true/false>
    }},
    "sources_checked": ["lista de URLs que visitaste"],
    "gemini_reasoning": "<una sola línea explicando la decisión más importante>"
}}

REGLAS:
- llm_veto = true SOLO ante eventos extraordinarios (hack masivo, caída exchange, regulación crítica)
- Si no encuentras información clara → usa valores neutrales (0)
- No especules — solo reporta hechos verificables
- La respuesta debe ser JSON válido, sin markdown, sin explicaciones fuera del JSON
"""


class GeminiIntelligenceAgent:
    """
    Agente de inteligencia de mercado basado en Gemini.

    Investiga el contexto de mercado crypto usando fuentes web públicas
    y genera un ContextReport estructurado para el MetaEvaluador.
    """

    def __init__(self) -> None:
        api_key = os.getenv('GEMINI_API_KEY', '')
        self._enabled = bool(api_key)
        if self._enabled:
            self._client = genai.Client(api_key=api_key)
        self._min_interval = int(
            os.getenv('GEMINI_MIN_REINVESTIGATE_INTERVAL', str(GEMINI_MIN_REINVESTIGATE))
        )

    async def get_context_report(
        self,
        last_report: Optional[dict],
        hour_utc: int,
        db_context: Optional[str] = None,
    ) -> dict:
        """
        Punto de entrada principal. Decide si re-investiga o reutiliza.
        Siempre devuelve un ContextReport válido.
        """
        if not self._enabled:
            return {**_NEUTRAL_REPORT, 'gemini_reasoning': 'Gemini deshabilitado — GEMINI_API_KEY no configurada'}

        if not self._should_reinvestigate(last_report):
            reuse = dict(last_report)
            reuse['was_reinvestigated'] = False
            reuse['reuse_count'] = last_report.get('reuse_count', 0) + 1
            return reuse

        return await self._run_investigation(hour_utc, db_context or '')

    def _should_reinvestigate(self, last_report: Optional[dict]) -> bool:
        """Re-investiga si no hay reporte previo o pasó el intervalo mínimo."""
        if not last_report:
            return True

        last_ts = last_report.get('_timestamp', 0)
        elapsed = time.time() - last_ts
        return elapsed >= self._min_interval

    async def _run_investigation(self, hour_utc: int, db_context: str) -> dict:
        """Llama a Gemini con prompt completo. Devuelve reporte o neutral si falla."""
        try:
            prompt = _INVESTIGATION_PROMPT.format(
                symbols=', '.join(SYMBOLS),
                hour_utc=hour_utc,
                db_context=db_context or 'Sin contexto histórico disponible.',
            )

            response = self._client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )
            raw_text = response.text.strip()

            report = self._parse_response(raw_text)
            report['was_reinvestigated'] = True
            report['reuse_count'] = 0
            report['_timestamp'] = time.time()
            report['full_report'] = report.copy()
            return report

        except Exception as e:
            return {**_NEUTRAL_REPORT, 'gemini_reasoning': f'Error Gemini: {e}'}

    def _parse_response(self, raw: str) -> dict:
        """Parsea JSON de Gemini. Si falla → devuelve reporte neutral."""
        try:
            if raw.startswith('```'):
                raw = raw.split('```')[1]
                if raw.startswith('json'):
                    raw = raw[4:]
            data = json.loads(raw.strip())

            return {
                'sentiment_score': float(
                    max(-1.0, min(1.0, data.get('sentiment_score', 0.0)))
                ),
                'whale_pressure': int(
                    max(-1, min(1, data.get('whale_pressure', 0)))
                ),
                'macro_bias': int(
                    max(-1, min(1, data.get('macro_bias', 0)))
                ),
                'news_risk_level': int(
                    max(0, min(2, data.get('news_risk_level', 0)))
                ),
                'optimal_hour': bool(data.get('optimal_hour', True)),
                'llm_veto': bool(data.get('llm_veto', False)),
                'significant_changes': data.get('significant_changes', {}),
                'sources_checked': data.get('sources_checked', []),
                'gemini_reasoning': str(data.get('gemini_reasoning', ''))[:500],
                'full_report': data,
            }
        except Exception:
            return dict(_NEUTRAL_REPORT)
