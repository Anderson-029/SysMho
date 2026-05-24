"""
SysMho — Orquestador Principal (Motor de IA).

Carga todos los submódulos, escucha al mercado y dispara alertas o
ejecuciones según las decisiones del modelo de Inteligencia Artificial
junto al Gestor de Riesgos.

Sistema de alertas:
  - REGULAR : Top 3 señales evaluadas cada 5 minutos.
  - BOUNTY  : Señal de alta convicción sin horario fijo (confianza ≥ 55%,
              tendencias 5m/1h/4h alineadas y R/R ≥ 3).
"""

from dotenv import load_dotenv
load_dotenv()

import asyncio
import builtins
import os
import signal
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from src.ai.meta_evaluator import MetaEvaluator
from src.ai.predictor import ModelPredictor
from src.ai.self_learner import SelfLearner
from src.ai.trainer import ModelTrainer
from src.analysis.features import FeatureEngineer
from src.collector.gap_filler import GapFiller
from src.collector.websocket import BinanceWebSocket
from src.constants import (
    SYMBOLS, DEFAULT_TIMEFRAME,
    TOP_N_SIGNALS, SIGNAL_SCAN_INTERVAL_SECONDS,
    BOUNTY_WATCHER_INTERVAL_SECONDS,
    SIGNAL_SCANNER_SECONDS,
    PENDING_SIGNAL_TIMEOUT_SECONDS,
    GEMINI_START_OFFSET_SECONDS,
    GEMINI_MAX_WAIT_SECONDS,
)
from src.database.repository import DatabaseRepository
from src.executor.circuit_breaker import CircuitBreaker
from src.executor.monitor import PositionMonitor
from src.executor.trader import TradeExecutor
from src.intelligence import GeminiIntelligenceAgent
from src.risk.manager import RiskManager

# ---- Configuración de autonomía ----
# AUTONOMOUS_MODE ya NO es una constante fija — se lee en runtime desde
# runtime_state.json para que el dashboard pueda togglarlo sin reiniciar.
from src.runtime_config import is_autonomous, set_autonomous, set_last_scan_at
from src.paths import BRAIN_LOG, ENGINE_HEARTBEAT
LEARNING_LOOP_SECONDS = int(os.getenv('LEARNING_LOOP_SECONDS', '60'))

# --- INTERCEPTOR DE PENSAMIENTO (Para el Dashboard Web) ---
log_file_path = BRAIN_LOG
with open(log_file_path, 'a', encoding='utf-8') as f:
    f.write("🧠 SysMho: Sistema Neuronal Iniciado...\n")


def sysmho_print(*args, **kwargs) -> None:
    """Escribe en la memoria visible web y luego a la consola normal."""
    line = " ".join(map(str, args))
    with open(log_file_path, 'a', encoding='utf-8', buffering=1) as log_f:
        log_f.write(line + "\n")
        log_f.flush()
    builtins.print(*args, **kwargs)


print = sysmho_print
# --------------------------------------------------------


def _get_trend(df_loc, pref: str = '') -> str:
    """Determina la tendencia (UP/DOWN/NEUTRAL) para un timeframe."""
    try:
        last = df_loc.iloc[-1]
        close = last['close']
        ema = last.get(f'{pref}ema_200')
        rsi = last.get(f'{pref}rsi_14')
        if ema is None or rsi is None:
            return 'NEUTRAL'
        if close > ema and rsi > 55:
            return 'UP'
        if close < ema and rsi < 45:
            return 'DOWN'
        return 'NEUTRAL'
    except Exception:
        return 'NEUTRAL'


class AutonomousBot:
    """Orquesta todos los sistemas de SysMho."""

    def __init__(
        self, symbols: Optional[List[str]] = None,
        timeframe: str = DEFAULT_TIMEFRAME
    ) -> None:
        self.symbols = symbols if symbols else SYMBOLS
        self.timeframe = timeframe
        self.is_running = False

        self.db = DatabaseRepository()
        self.ws = BinanceWebSocket(use_auth=False, db=self.db)
        self.engineer = FeatureEngineer(db=self.db)
        self.predictor = ModelPredictor()

        self.risk_manager = RiskManager(db=self.db)
        self.trader = TradeExecutor(db=self.db)
        self.trainer = ModelTrainer(db=self.db)
        self.monitor = PositionMonitor(db=self.db, trader=self.trader)

        self.last_trained_counts = {s: 0 for s in self.symbols}
        self.active_handlers: set = set()

        # ── Módulos de autonomía ─────────────────────────────────────────
        self.circuit_breaker = CircuitBreaker()
        self.meta_evaluator = MetaEvaluator()
        self.self_learner = SelfLearner()
        self.gemini_agent = GeminiIntelligenceAgent()

        print("\n" + "=" * 55)
        print("🛡️  [MODO SEGURO ACTIVO — 2% Riesgo]")
        print("📊  [REGULAR] Top 3 señales cada 5 minutos")
        print("🏆  [BOUNTY ] Alta convicción sin horario fijo")
        print("=" * 55 + "\n")

    # ------------------------------------------------------------------ #
    #  EVALUACIÓN UNITARIA DE UN SÍMBOLO                                  #
    # ------------------------------------------------------------------ #

    async def _evaluate_symbol(self, symbol: str) -> Optional[dict]:
        """
        Obtiene datos, calcula predicción, auditoría y score para un activo.

        Returns:
            Dict con prediction, dictamen, tendencias, rr_ratio y score.
            None si hay error o datos insuficientes.
        """
        try:
            df = await self.engineer.get_master_dataframe(
                symbol, self.timeframe, limit=1000
            )
            if len(df) < 20:
                return None

            prediction = self.predictor.predict_signal(df, aggressive=False)
            if prediction['signal_int'] == 0:
                return None

            trend_5m = _get_trend(df)
            trend_1h = _get_trend(df, 'h1_')
            trend_4h = _get_trend(df, 'h4_')

            balance = await self.trader.get_portfolio_balance()
            current_market = {
                'close': float(df['close'].iloc[-1]),
                'atr_14': float(df['atr_14'].iloc[-1]),
            }

            dictamen = await self.risk_manager.evaluate_signal(
                symbol, prediction, current_market, balance
            )

            if not dictamen.get('approved'):
                return None

            profit = dictamen.get('potential_profit_usdt', 0.0)
            loss = dictamen.get('potential_loss_usdt', 0.01)
            rr_ratio = profit / max(loss, 0.01)

            score = self.predictor.compute_score(
                prediction, trend_5m, trend_1h, trend_4h, rr_ratio
            )

            return {
                'prediction': prediction,
                'dictamen': dictamen,
                'trend_5m': trend_5m,
                'trend_1h': trend_1h,
                'trend_4h': trend_4h,
                'rr_ratio': rr_ratio,
                'score': score,
            }

        except Exception as e:
            print(f"⚠️ [EVAL {symbol}]: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  ALMACENAMIENTO DE SEÑAL                                            #
    # ------------------------------------------------------------------ #

    async def _store_signal(
        self,
        symbol: str,
        eval_data: dict,
        alert_category: str = 'REGULAR',
    ) -> None:
        """Inserta señal en pending_approvals y lanza su task de espera."""
        prediction = eval_data['prediction']
        dictamen = eval_data['dictamen']
        trend_5m = eval_data['trend_5m']
        trend_1h = eval_data['trend_1h']
        trend_4h = eval_data['trend_4h']
        score = eval_data.get('score', 0.0)

        qty = dictamen.get('suggested_quantity', dictamen['quantity'])
        final_type = prediction.get('signal_type', 'STANDARD')

        query_ins = '''
            INSERT INTO pending_approvals (
                symbol, side, quantity, entry_price,
                stop_loss, take_profit, risk_score,
                invested_usdt, win_probability,
                loss_probability, potential_profit_usdt,
                potential_loss_usdt, exposure_warning,
                signal_type, trend_5m, trend_1h, trend_4h,
                alert_category, score
            ) VALUES (
                $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
                $11,$12,$13,$14,$15,$16,$17,$18,$19
            ) RETURNING id
        '''
        async with self.db.pool.acquire() as conn:
            pending_id = await conn.fetchval(
                query_ins,
                symbol, prediction['signal_str'],
                qty, dictamen['entry_price'],
                dictamen['stop_loss'], dictamen['take_profit'],
                float(prediction['confidence']),
                dictamen['invested_usdt'],
                dictamen['win_probability'],
                dictamen['loss_probability'],
                dictamen['potential_profit_usdt'],
                dictamen['potential_loss_usdt'],
                dictamen.get('exposure_warning', False),
                final_type, trend_5m, trend_1h, trend_4h,
                alert_category, float(score),
            )

        icon = '🏆' if alert_category == 'BOUNTY' else '📊'
        print(
            f"{icon} [{alert_category}] {symbol} | "
            f"{prediction['signal_str']} | "
            f"Score: {score:.3f} | "
            f"Conf: {prediction['confidence']:.1%} | "
            f"R/R: {eval_data.get('rr_ratio', 0):.1f}"
        )

        self.active_handlers.add(pending_id)
        asyncio.create_task(self._process_signal_task(symbol, pending_id))

    # ------------------------------------------------------------------ #
    #  GEMINI INTELLIGENCE LOOP — MINUTO 3:45 DE CADA CICLO              #
    # ------------------------------------------------------------------ #

    async def _gemini_intelligence_loop(self) -> None:
        """
        Corre en paralelo con el scanner 5m.
        En cada ciclo espera hasta el segundo 225 (minuto 3:45) y lanza
        la investigación de mercado con Gemini. El reporte queda en BD
        listo para que XGBoost lo use al minuto 5.
        """
        import time as _time
        print("🔍 [GEMINI] Intelligence Loop iniciado — investigación en minuto 3:45")

        while self.is_running:
            cycle_start = _time.time()
            try:
                # Esperar hasta el segundo 225 del ciclo (minuto 3:45)
                while _time.time() - cycle_start < GEMINI_START_OFFSET_SECONDS:
                    if not self.is_running:
                        return
                    await asyncio.sleep(5)

                hour_utc = datetime.now(timezone.utc).hour

                # Contexto de BD para enriquecer el prompt
                db_context = await self._build_gemini_db_context()

                # Obtener reporte anterior (para lógica de re-investigación)
                try:
                    last_report = await self.db.get_latest_gemini_context()
                except Exception:
                    last_report = None

                # Ejecutar investigación con timeout
                report = await asyncio.wait_for(
                    self.gemini_agent.get_context_report(
                        last_report, hour_utc, db_context
                    ),
                    timeout=GEMINI_MAX_WAIT_SECONDS,
                )

                await self.db.save_gemini_context(report)

                reused = not report.get('was_reinvestigated', True)
                tag = 'REUTILIZADO' if reused else 'NUEVO'
                print(
                    f"🔍 [GEMINI] Reporte {tag} — "
                    f"veto={report['llm_veto']} "
                    f"sentiment={report['sentiment_score']:+.2f} "
                    f"macro={'BULL' if report['macro_bias']==1 else 'BEAR' if report['macro_bias']==-1 else 'NEUTRAL'}"
                )

            except asyncio.TimeoutError:
                print("⚠️ [GEMINI] Timeout — XGBoost operará con sus 28 features")
            except Exception as e:
                print(f"⚠️ [GEMINI ERROR]: {e}")

            # Esperar hasta completar el ciclo de 5 minutos
            elapsed = _time.time() - cycle_start
            remaining = SIGNAL_SCAN_INTERVAL_SECONDS - elapsed
            await asyncio.sleep(max(remaining, 0))

    async def _build_gemini_db_context(self) -> str:
        """Construye contexto de BD para enriquecer el prompt de Gemini."""
        try:
            stats = await self.db.get_daily_stats()
            hour_utc = datetime.now(timezone.utc).hour
            lines = [
                f"Hora actual UTC: {hour_utc}:00",
                f"Trades hoy: {stats.get('trades_today', 0)}",
                f"PnL diario: {stats.get('daily_pnl_pct', 0)*100:+.2f}%",
                f"Pérdidas consecutivas: {stats.get('consecutive_losses', 0)}",
                f"Balance: ${stats.get('total_balance', 0):.2f}",
            ]
            return ' | '.join(lines)
        except Exception:
            return ''

    # ------------------------------------------------------------------ #
    #  SCANNER REGULAR — TOP 3 CADA 5 MINUTOS                            #
    # ------------------------------------------------------------------ #

    async def _5min_scanner(self) -> None:
        """Cada 5 min evalúa los 10 activos y guarda los Top 3 (REGULAR)."""
        import time as _time
        print(
            f"📊 [SCANNER 5M] Iniciando — "
            f"Top {TOP_N_SIGNALS} señales cada "
            f"{SIGNAL_SCAN_INTERVAL_SECONDS // 60} minutos."
        )

        # Sincronización al reiniciar: espera el tiempo restante del ciclo anterior.
        # Evita que el primer scan ocurra inmediatamente si el sistema se reinició
        # antes de que terminara el ciclo de 5 minutos.
        try:
            async with self.db.pool.acquire() as conn:
                last_scan = await conn.fetchval(
                    "SELECT MAX(created_at) FROM pending_approvals "
                    "WHERE alert_category = 'REGULAR'"
                )
            if last_scan:
                elapsed = _time.time() - last_scan.timestamp()
                wait = SIGNAL_SCAN_INTERVAL_SECONDS - elapsed
                if wait > 5:
                    print(
                        f"📊 [SCANNER 5M] Sincronizando con ciclo anterior — "
                        f"próximo scan en {wait:.0f}s"
                    )
                    await asyncio.sleep(wait)
        except Exception:
            pass  # Si falla la consulta, arranca el ciclo normalmente

        while self.is_running:
            try:
                await self._run_5min_scan()
            except Exception as e:
                print(f"⚠️ [SCANNER 5M ERROR]: {e}")
            await asyncio.sleep(SIGNAL_SCAN_INTERVAL_SECONDS)

    async def _run_5min_scan(self) -> None:
        """Lógica de un ciclo de escaneo regular."""
        time_str = datetime.now().strftime('%H:%M:%S')
        set_last_scan_at()  # Siempre registrar, aunque todos queden en WAIT
        print(
            f"\n[{time_str}] 📊 [5M SCAN] "
            f"Evaluando {len(self.symbols)} activos..."
        )

        results = await asyncio.gather(
            *[self._evaluate_symbol(s) for s in self.symbols],
            return_exceptions=True,
        )

        candidates = [
            (sym, res)
            for sym, res in zip(self.symbols, results)
            if res and not isinstance(res, Exception)
        ]

        if not candidates:
            print(f"[{time_str}] 📊 [5M SCAN] Todos los activos en WAIT.")
            open(ENGINE_HEARTBEAT, 'w').close()
            return

        candidates.sort(key=lambda x: x[1].get('score', 0.0), reverse=True)
        top = candidates[:TOP_N_SIGNALS]

        # Descartar REGULAR anteriores sin resolver
        async with self.db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE pending_approvals "
                "SET status = 'DISMISSED', resolved_at = NOW() "
                "WHERE status = 'PENDING' AND alert_category = 'REGULAR'"
            )

        print(
            f"[{time_str}] 📊 [5M SCAN] "
            f"{len(top)} candidato(s) seleccionado(s):"
        )
        for sym, data in top:
            await self._store_signal(sym, data, alert_category='REGULAR')

        open(ENGINE_HEARTBEAT, 'w').close()

    # ------------------------------------------------------------------ #
    #  BOUNTY WATCHER — ALTA CONVICCIÓN SIN HORARIO                      #
    # ------------------------------------------------------------------ #

    async def _bounty_watcher(self) -> None:
        """Cada 30s busca señales de alta convicción (BOUNTY)."""
        print(
            f"🏆 [BOUNTY WATCHER] Iniciando — "
            f"Umbral: {int(self.predictor.model is not None and 55)}% conf "
            f"+ 3 tendencias + R/R ≥ 3."
        )
        while self.is_running:
            try:
                await self._hunt_bounty()
            except Exception as e:
                print(f"⚠️ [BOUNTY ERROR]: {e}")
            await asyncio.sleep(BOUNTY_WATCHER_INTERVAL_SECONDS)

    async def _hunt_bounty(self) -> None:
        """Evalúa todos los activos buscando condiciones de BOUNTY."""
        results = await asyncio.gather(
            *[self._evaluate_symbol(s) for s in self.symbols],
            return_exceptions=True,
        )

        for sym, res in zip(self.symbols, results):
            if not res or isinstance(res, Exception):
                continue

            prediction = res['prediction']
            if not self.predictor.is_bounty(
                prediction,
                res['trend_5m'], res['trend_1h'], res['trend_4h'],
                res.get('rr_ratio', 0.0),
            ):
                continue

            # Anti-spam: solo un BOUNTY activo por símbolo
            async with self.db.pool.acquire() as conn:
                existing = await conn.fetchval(
                    "SELECT id FROM pending_approvals "
                    "WHERE symbol = $1 AND status = 'PENDING' "
                    "AND alert_category = 'BOUNTY'",
                    sym,
                )
            if existing:
                continue

            await self._store_signal(sym, res, alert_category='BOUNTY')

    # ------------------------------------------------------------------ #
    #  SCANNER DE HUÉRFANAS (señales manuales / recuperación)             #
    # ------------------------------------------------------------------ #

    async def _continuous_signal_scanner(self) -> None:
        """Detecta señales sin task activa (inyectadas manualmente o por recovery)."""
        print("📡 [SCANNER] Iniciando monitor de señales huérfanas...")
        while self.is_running:
            try:
                await self._scan_and_dispatch_signals()
            except Exception as e:
                print(f"⚠️ [SCANNER ERROR]: {e}")
            await asyncio.sleep(SIGNAL_SCANNER_SECONDS)

    async def _scan_and_dispatch_signals(self) -> None:
        query = '''
            SELECT id, symbol, status FROM pending_approvals
            WHERE status IN ('PENDING', 'APPROVED')
        '''
        async with self.db.pool.acquire() as conn:
            orphans = await conn.fetch(query)

        for orphan in orphans:
            p_id = orphan['id']
            if p_id not in self.active_handlers:
                print(
                    f"🔄 [SYNC] Detectada #{p_id} ({orphan['symbol']}) "
                    f"— Est: {orphan['status']}"
                )
                self.active_handlers.add(p_id)
                asyncio.create_task(
                    self._process_signal_task(orphan['symbol'], p_id)
                )

    # ------------------------------------------------------------------ #
    #  PROCESAMIENTO Y EJECUCIÓN DE SEÑALES                              #
    # ------------------------------------------------------------------ #

    async def _process_signal_task(self, symbol: str, pending_id: int) -> None:
        """Wrapper con finally para limpiar el registro de handlers activos."""
        try:
            await self._handle_pending_approval(symbol, pending_id, None)
        finally:
            self.active_handlers.discard(pending_id)

    async def _autonomous_decide(
        self, symbol: str, pending_id: int, dictamen: dict
    ) -> str:
        """
        Toma una decisión autónoma sobre una señal.

        Flujo:
          1. CircuitBreaker — condiciones sistémicas duras
          2. MetaEvaluator — filtro estadístico de segunda capa
          3. Escribe decisión a BD (autonomous_decisions)
          4. Actualiza pending_approvals con APPROVED / REJECTED

        Returns: 'APPROVED' | 'REJECTED'
        """
        # pending_approvals usa win_probability (no confidence) y side (no direction)
        confidence = float(dictamen.get('win_probability') or dictamen.get('confidence') or 0.0)
        side = dictamen.get('side', 'BUY')
        direction = 'LONG' if side == 'BUY' else 'SHORT'

        # ── 0. Ventana horaria destructiva ───────────────────────────────
        # No es veto — eleva el umbral del MetaEvaluador en +0.08.
        # Buenas señales igual pasan; señales débiles no.
        # Temporal: cuando by_hour acumule >= 5 trades, el componente
        # de WR por hora del MetaEvaluador lo maneja automáticamente.
        from src.constants import (
            DESTRUCTIVE_HOUR_START, DESTRUCTIVE_HOUR_END, DESTRUCTIVE_HOUR_PENALTY
        )
        _dh_start  = int(os.getenv('DESTRUCTIVE_HOUR_START', str(DESTRUCTIVE_HOUR_START)))
        _dh_end    = int(os.getenv('DESTRUCTIVE_HOUR_END',   str(DESTRUCTIVE_HOUR_END)))
        _penalty   = float(os.getenv('DESTRUCTIVE_HOUR_PENALTY', str(DESTRUCTIVE_HOUR_PENALTY)))
        _hour_utc  = datetime.now(timezone.utc).hour
        _window_penalty = _penalty if _dh_start <= _hour_utc < _dh_end else 0.0

        if _window_penalty > 0:
            print(
                f"⚠️ [AUTONOMÍA] {symbol} en ventana {_dh_start}-{_dh_end}h UTC — "
                f"umbral +{_window_penalty:.2f} (más exigente)"
            )

        # ── 1. CircuitBreaker ────────────────────────────────────────────
        try:
            stats = await self.db.get_daily_stats()
        except Exception as e:
            print(f"⚠️ [AUTONOMÍA] Error obteniendo stats diarias: {e}")
            stats = {
                'trades_today': 0, 'daily_pnl_pct': 0.0,
                'weekly_pnl_pct': 0.0, 'consecutive_losses': 0,
                'recent_trades': [],
            }

        async with self.db.pool.acquire() as conn:
            open_count = await conn.fetchval(
                "SELECT COUNT(*) FROM positions"
            ) or 0

        cb_triggered, cb_reason = self.circuit_breaker.check(
            open_positions=int(open_count),
            daily_trades=stats.get('trades_today', 0),
            consecutive_losses=stats.get('consecutive_losses', 0),
            daily_pnl_pct=stats.get('daily_pnl_pct', 0.0),
            weekly_pnl_pct=stats.get('weekly_pnl_pct', 0.0),
        )

        if cb_triggered:
            print(f"🛑 [AUTONOMÍA] ── Circuit Breaker ACTIVO ──────────────────")
            print(f"🛑 [AUTONOMÍA] {symbol} {direction} bloqueada")
            print(f"🛑 [AUTONOMÍA] Motivo: {cb_reason}")
            print(f"🛑 [AUTONOMÍA] Contexto → Pos: {int(open_count)} | Trades hoy: {stats.get('trades_today',0)} | Racha: {stats.get('consecutive_losses',0)} pérd.")
            print(f"🛑 [AUTONOMÍA] ────────────────────────────────────────────")
            await self.db.log_autonomous_decision(
                pending_id=pending_id,
                symbol=symbol,
                decision='REJECTED',
                meta_score=0.0,
                confidence=confidence,
                direction=direction,
                reasons=[cb_reason],
                cb_active=True,
                cb_reason=cb_reason,
            )
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE pending_approvals SET status='REJECTED', "
                    "resolved_at=NOW() WHERE id=$1", pending_id
                )
            return 'REJECTED'

        # ── 2. MetaEvaluator ─────────────────────────────────────────────
        self.meta_evaluator.reload_stats()
        try:
            gemini_context = await self.db.get_latest_gemini_context()
        except Exception:
            gemini_context = None
        meta_score, approved, reasons = self.meta_evaluator.evaluate(
            signal=dictamen,
            recent_trades=stats.get('recent_trades', []),
            window_penalty=_window_penalty,
            gemini_context=gemini_context,
        )

        decision = 'APPROVED' if approved else 'REJECTED'
        icon = '✅' if approved else '❌'
        print(f"🤖 [AUTONOMÍA] ── MetaEvaluador #{pending_id} ─────────────────")
        print(f"🤖 [AUTONOMÍA] {icon} {symbol} {direction} → {decision}")
        print(f"🤖 [AUTONOMÍA] MetaScore: {meta_score:.3f} | Conf: {confidence*100:.1f}% | Umbral: {os.getenv('META_SCORE_THRESHOLD','0.52')}")
        for r in reasons:
            print(f"🤖 [AUTONOMÍA]   {r}")
        print(f"🤖 [AUTONOMÍA] ────────────────────────────────────────────")

        # ── 3. Log en BD ─────────────────────────────────────────────────
        try:
            await self.db.log_autonomous_decision(
                pending_id=pending_id,
                symbol=symbol,
                decision=decision,
                meta_score=meta_score,
                confidence=confidence,
                direction=direction,
                reasons=reasons,
                cb_active=False,
                cb_reason='',
            )
        except Exception as e:
            print(f"⚠️ [AUTONOMÍA] Error guardando decisión: {e}")

        # ── 4. Actualizar pending_approvals ──────────────────────────────
        async with self.db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE pending_approvals SET status=$1, "
                "resolved_at=NOW() WHERE id=$2",
                decision, pending_id
            )

        return decision

    async def _handle_pending_approval(
        self, symbol: str, pending_id: int, dictamen: Optional[dict]
    ) -> None:
        """
        Gestiona la aprobación de una señal.

        En modo manual: espera decisión del operador (timeout 5 min).
        En modo autónomo: delega de inmediato al MetaEvaluador.
        """
        # ── Cargar dictamen si no fue pasado ─────────────────────────────
        if not dictamen:
            try:
                async with self.db.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM pending_approvals WHERE id = $1", pending_id
                    )
                if row:
                    dictamen = {
                        k: (float(v) if isinstance(v, (Decimal, float)) else v)
                        for k, v in dict(row).items()
                    }
            except Exception:
                pass

        # ── Modo Autónomo ────────────────────────────────────────────────
        if is_autonomous():
            if dictamen:
                status = await self._autonomous_decide(symbol, pending_id, dictamen)
            else:
                print(f"⚠️ [AUTONOMÍA] No se pudo cargar dictamen #{pending_id}. Omitiendo.")
                return
        else:
            # ── Modo Manual: esperar operador ────────────────────────────
            status = 'PENDING'
            start_time = datetime.now()

            while status == 'PENDING' and self.is_running:
                await asyncio.sleep(0.2)

                if (datetime.now() - start_time).total_seconds() > PENDING_SIGNAL_TIMEOUT_SECONDS:
                    print(
                        f"⏰ [{symbol}] Señal #{pending_id} expirada "
                        f"({PENDING_SIGNAL_TIMEOUT_SECONDS}s). Auto-descartada."
                    )
                    try:
                        async with self.db.pool.acquire() as conn:
                            await conn.execute(
                                "UPDATE pending_approvals "
                                "SET status = 'DISMISSED', resolved_at = NOW() "
                                "WHERE id = $1", pending_id
                            )
                    except Exception:
                        pass
                    return

                try:
                    async with self.db.pool.acquire() as conn:
                        status = await conn.fetchval(
                            "SELECT status FROM pending_approvals WHERE id = $1",
                            pending_id,
                        )
                except Exception:
                    await asyncio.sleep(1)

        if status == 'APPROVED':
            print(f"✅ [MANDO] #{pending_id} ({symbol}) APROBADA. Ejecutando...")

            if not dictamen:
                print("⚠️ [AVISO] Reconstruyendo parámetros del dictamen...")
                async with self.db.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM pending_approvals WHERE id = $1",
                        pending_id,
                    )
                    if row:
                        dictamen = {
                            k: (float(v) if isinstance(v, (Decimal, float)) else v)
                            for k, v in dict(row).items()
                        }

            if dictamen:
                try:
                    res = await self.trader.execute_trade(dictamen)
                    new_status = 'EXECUTED' if res.get('success') else 'FAILED'
                    if res.get('success'):
                        print(f"💸 [ÉXITO] Operación {symbol} enviada!")
                    else:
                        print(f"❌ [FALLO] Error orden #{pending_id}: {res.get('error')}")
                except Exception as e:
                    print(f"❌ [CRÍTICO] Error en orden #{pending_id}: {e}")
                    new_status = 'FAILED'

                async with self.db.pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE pending_approvals "
                        "SET status = $1, resolved_at = NOW() WHERE id = $2",
                        new_status, pending_id,
                    )
            else:
                print(f"❌ [FALLO] No se pudo recuperar dictamen (#{pending_id}).")

        elif status == 'REJECTED':
            print(f"🛑 [MANDO] Orden #{pending_id} ({symbol}) RECHAZADA.")
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE pending_approvals "
                    "SET status = 'REJECTED', resolved_at = NOW() WHERE id = $1",
                    pending_id,
                )

    # ------------------------------------------------------------------ #
    #  LOOPS DE SOPORTE                                                   #
    # ------------------------------------------------------------------ #

    async def _learning_loop(self) -> None:
        """
        Ciclo de aprendizaje continuo: actualiza meta_stats.json con los
        trades cerrados recientemente y recarga el MetaEvaluador.

        Intervalo: LEARNING_LOOP_SECONDS (default 60s).
        """
        print("📈 [SelfLearner] Loop de aprendizaje iniciado.")
        last_processed_id: int = 0

        while self.is_running:
            try:
                # Obtener trades cerrados no procesados todavía
                async with self.db.pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT id, symbol, side, pnl,
                               price, executed_at
                        FROM trades
                        WHERE status = 'CLOSED'
                          AND id > $1
                        ORDER BY id ASC
                        LIMIT 50
                        """,
                        last_processed_id,
                    )

                for row in rows:
                    trade = dict(row)
                    # Normalizar campos al formato que entiende SelfLearner
                    trade['pnl_usdt'] = float(trade.get('pnl') or 0)
                    trade['direction'] = 'LONG' if trade.get('side') == 'BUY' else 'SHORT'
                    trade['opened_at'] = trade.get('executed_at')
                    trade['entry_price'] = float(trade.get('price') or 1)
                    trade['exit_price'] = trade['entry_price']  # precio único en trades
                    self.self_learner.update(trade)
                    last_processed_id = trade['id']

                if rows:
                    self.meta_evaluator.reload_stats()
                    summary = self.self_learner.summary()
                    print(
                        f"📈 [SelfLearner] {len(rows)} trade(s) aprendidos | "
                        f"Total: {summary['total_trades']} | "
                        f"WR global: {summary['global_win_rate']*100:.1f}%"
                    )

            except Exception as e:
                print(f"⚠️ [SelfLearner] Error en loop de aprendizaje: {e}")

            await asyncio.sleep(LEARNING_LOOP_SECONDS)

    async def _auto_train_loop(self) -> None:
        """Evalúa ciclo de evolución XGBoost cada hora (+1000 velas nuevas)."""
        while self.is_running:
            try:
                trigger = False
                for sym in self.symbols:
                    c = await self.db.get_market_data_count(sym, self.timeframe)
                    if self.last_trained_counts[sym] == 0:
                        self.last_trained_counts[sym] = c
                        print(f"📊 [Evolución {sym}] Base: {c} velas.")
                        continue
                    if c - self.last_trained_counts[sym] >= 1000:
                        print(f"\n✨ [HITO] {sym} +1000 velas! Evolucionando...")
                        trigger = True

                if trigger:
                    await self.trainer.train_model(self.symbols, self.timeframe)
                    for s in self.symbols:
                        self.last_trained_counts[s] = \
                            await self.db.get_market_data_count(s, self.timeframe)
                    print("✅ [Evolución] Motor de IA Universal refinado.")

                await asyncio.sleep(3600)
            except Exception as e:
                print(f"⚠️ [Error en Evolución]: {e}")
                await asyncio.sleep(600)

    async def _accounting_sync_loop(self) -> None:
        """Garante de la Contabilidad Triple Portafolio."""
        print("🛡️ [GUARD] Testeando sincronía contable en DB...")
        while self.is_running:
            try:
                async with self.db.pool.acquire() as conn:
                    m = await conn.fetchval(
                        "SELECT COALESCE(SUM(invested_usdt), 0) FROM positions"
                    )
                    real_margin = float(m or 0)

                    p = await conn.fetchrow(
                        "SELECT id, available_balance, in_positions, total_balance "
                        "FROM portfolio ORDER BY recorded_at DESC LIMIT 1"
                    )
                    if p:
                        diff = float(p['in_positions']) - real_margin
                        if abs(diff) > 0.0001:
                            print(f"⚖️ [SYNC] Desajuste contable: ${diff:.4f}. Corrigiendo.")
                            n_av = float(p['available_balance']) + diff
                            await conn.execute(
                                "UPDATE portfolio SET available_balance=$1, "
                                "in_positions=$2, total_balance=$3 WHERE id=$4",
                                n_av, real_margin, n_av + real_margin, p['id'],
                            )
            except Exception as e:
                print(f"⚠️ [Accounting Sync Error]: {e}")
            await asyncio.sleep(300)

    async def _api_health_monitor_loop(self) -> None:
        """Verifica la conectividad REST con Binance cada 30 segundos."""
        print("🛡️ [HEALTH MONITOR] Iniciando vigilancia REST continua...")
        await self.trader.check_api_link()
        while self.is_running:
            try:
                await self.trader.check_api_link()
            except Exception as e:
                print(f"⚠️ [HEALTH MONITOR] Fallo en ping: {e}")
            await asyncio.sleep(30)

    # ------------------------------------------------------------------ #
    #  RECONCILIACIÓN DE ARRANQUE                                        #
    # ------------------------------------------------------------------ #

    async def _startup_reconciliation(self) -> None:
        """
        Reconcilia el estado de la BD contra Binance al arrancar el Motor.

        Detecta y corrige tres condiciones antes de iniciar cualquier loop:
          1. Posiciones en BD que Binance ya no tiene (cerradas externamente) → BINANCE_SYNC
          2. Posiciones con lado incorrecto (BD=SELL vs Binance=BUY) → SIDE_MISMATCH fix
          3. Portfolio desactualizado → sobrescribir con balance real de Binance

        Si Binance no responde, se omite y el motor arranca con los datos locales.
        """
        print("🔍 [STARTUP] Reconciliando estado BD vs Binance...")

        # 1. Obtener posiciones reales de Binance
        official_details = await self.trader.get_active_positions_details()
        if official_details is None:
            print("⚠️ [STARTUP] Binance no respondió — reconciliación omitida, arrancando con BD actual.")
            return

        # 2. Obtener posiciones locales
        async with self.db.pool.acquire() as conn:
            positions = await conn.fetch("SELECT * FROM positions")

        for pos in positions:
            symbol = pos['symbol']
            official = official_details.get(symbol)

            if official is None:
                # Posición en BD que Binance no tiene → fue cerrada externamente
                print(f"📡 [STARTUP] {symbol} no existe en Binance — sincronizando cierre en BD...")
                await self.monitor._close_position(
                    pos, 0.0, float(pos['pnl_unrealized'] or 0), "BINANCE_SYNC"
                )
            elif official['side'] != pos['side']:
                # Lado incorrecto → corregir registro local
                await self.monitor._correct_side_mismatch(pos, official)

        # 3. Sincronizar portfolio desde Binance con valores reales
        try:
            balance = await self.trader.exchange.fetch_balance()
            info = balance.get('info', {})
            available = float(info.get('availableBalance', 0.0))
            total = float(info.get('totalMarginBalance', info.get('totalWalletBalance', available)))

            async with self.db.pool.acquire() as conn:
                in_pos = await conn.fetchval(
                    "SELECT COALESCE(SUM(invested_usdt), 0) FROM positions"
                )

            await self.db.sync_wallet_from_exchange(available, total, float(in_pos or 0))
            print(
                f"✅ [STARTUP] Portfolio sincronizado — "
                f"total: ${total:.2f}, disponible: ${available:.2f}, en posiciones: ${float(in_pos or 0):.2f}"
            )
        except Exception as e:
            print(f"⚠️ [STARTUP] Error sincronizando portfolio desde Binance: {e}")

        print("✅ [STARTUP] Reconciliación completada.")

    # ------------------------------------------------------------------ #
    #  ARRANQUE                                                           #
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        """Despliega todas las neuronas asíncronamente."""
        self.is_running = True
        print(f"\n🚀 IGNICIÓN: Conectando {len(self.symbols)} activos...\n")
        await self.db.connect()
        await self._startup_reconciliation()

        # ── Relleno de vacíos históricos ────────────────────────────────
        try:
            gap_filler = GapFiller(db=self.db)
            await gap_filler.fill_all_gaps(self.symbols)
        except Exception as e:
            print(f"⚠️ [GAP FILLER] Error en sincronización de datos: {e}")
            print(f"⚠️ [GAP FILLER] Continuando arranque sin relleno completo.")

        # Log inicial del modo de operación
        if is_autonomous():
            print("🤖 [AUTONOMÍA] ══════════════════════════════════════")
            print("🤖 [AUTONOMÍA] MODO AUTÓNOMO ACTIVO al arrancar")
            print(f"🤖 [AUTONOMÍA] Umbral MetaScore: {os.getenv('META_SCORE_THRESHOLD','0.52')} | CB params: pos≤{os.getenv('CB_MAX_POSITIONS','3')} trades≤{os.getenv('CB_MAX_DAILY_TRADES','8')} racha≤{os.getenv('CB_MAX_CONSEC_LOSSES','3')}")
            print("🤖 [AUTONOMÍA] ══════════════════════════════════════")
        else:
            print("🖐 [AUTONOMÍA] Modo MANUAL — aprobación humana requerida")

        loop = asyncio.get_event_loop()

        def _shutdown_handler():
            print("\n[!] Señal [CTRL+C] recibida. Interrumpiendo.")
            for task in asyncio.all_tasks(loop):
                task.cancel()

        try:
            loop.add_signal_handler(signal.SIGINT, _shutdown_handler)
        except NotImplementedError:
            print("⚠️ [STARTUP] Registro de señal SIGINT no soportado por este event loop; se usará KeyboardInterrupt por defecto.")
        except Exception:
            raise

        tasks = [
            asyncio.create_task(self._continuous_signal_scanner()),
            asyncio.create_task(self._accounting_sync_loop()),
            asyncio.create_task(self._api_health_monitor_loop()),
            asyncio.create_task(self._5min_scanner()),
            asyncio.create_task(self._bounty_watcher()),
            asyncio.create_task(self._auto_train_loop()),
            asyncio.create_task(self._learning_loop()),
            asyncio.create_task(self.monitor.start_monitoring()),
            asyncio.create_task(self._gemini_intelligence_loop()),
        ]

        # WebSocket de velas para los 3 timeframes de cada activo
        for sym in self.symbols:
            tasks.append(asyncio.create_task(
                self.ws.watch_ohlcv(sym, self.timeframe)
            ))
            tasks.append(asyncio.create_task(self.ws.watch_ohlcv(sym, '1h')))
            tasks.append(asyncio.create_task(self.ws.watch_ohlcv(sym, '4h')))

        print(f"\n{'═'*54}")
        print(f"  ✅  CEREBRO SYSMHO OPERATIVO")
        print(f"  ✅  {len(self.symbols)} activos | {len(tasks)} módulos activos")
        print(f"{'═'*54}\n")

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            print("Apagando centros nerviosos ordenadamente...")
            await self.ws.close()
            self.is_running = False
            await self.trader.close_connection()
            await self.db.close()
            print("🛑 Bot en descanso total.")


if __name__ == "__main__":
    bot = AutonomousBot()
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        pass
