"""
SysMho — Motor de Backtest Histórico.

Simula operaciones pasadas usando los datos en PostgreSQL y el modelo XGBoost v3
para medir el rendimiento real del sistema antes de operar con dinero real.

Uso:
    python -m src.ai.backtest                        # Todos los activos
    python -m src.ai.backtest --symbol BTC/USDT      # Un activo
    python -m src.ai.backtest --min-confidence 0.55  # Solo alta convicción
    python -m src.ai.backtest --save results.csv     # Exportar resultados
"""

import argparse
import asyncio
import sys
from datetime import datetime

import numpy as np
import pandas as pd

from src.analysis.features import FeatureEngineer
from src.constants import (
    BOUNTY_CONFIDENCE_THRESHOLD,
    BOUNTY_MIN_RR_RATIO,
    BOUNTY_TREND_ALIGNMENT_REQUIRED,
    HIGH_CONVICTION_THRESHOLD,
    NORMAL_ATR_SL,
    NORMAL_ATR_TP,
    NORMAL_INERTIA_THRESHOLD,
    NORMAL_MIN_CONFIDENCE,
    NORMAL_STRENGTH_RATIO,
    SYMBOLS,
)
from src.database.repository import DatabaseRepository


class BacktestEngine:
    """Motor de simulación histórica — usa la misma lógica que el sistema en vivo."""

    def __init__(self):
        self.db = DatabaseRepository()
        self.feature_engineer = FeatureEngineer(db=self.db)
        self._model = None
        self._features = None
        self._load_model()

    def _load_model(self):
        """Carga el modelo XGBoost en memoria."""
        import os
        import joblib
        from src.paths import MODEL_PATH
        if not os.path.exists(MODEL_PATH):
            print("❌ Modelo no encontrado. Entrena primero con: python -m src.ai.trainer")
            sys.exit(1)
        self._model, self._features = joblib.load(MODEL_PATH)
        print(f"✅ Modelo cargado — {len(self._features)} features")

    def _batch_predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ejecuta predict_proba sobre todo el DataFrame de una vez (vectorizado).
        Aplica los mismos filtros que ModelPredictor.predict_signal() pero en batch.

        Returns DataFrame con columnas: signal_int, confidence, is_bounty
        """
        X = df[self._features].values
        all_probs = self._model.predict_proba(X)  # (n, 3): [SELL, WAIT, BUY]

        prob_sell = all_probs[:, 0]
        prob_wait = all_probs[:, 1]
        prob_buy  = all_probs[:, 2]

        # ── Filtro de inercia (veto)
        is_inert = prob_wait > NORMAL_INERTIA_THRESHOLD

        # ── Dirección dominante
        buy_dominant = prob_buy >= prob_sell
        pred_conf    = np.where(buy_dominant, prob_buy, prob_sell)
        opp_conf     = np.where(buy_dominant, prob_sell, prob_buy)

        strength_ratio  = pred_conf / np.maximum(opp_conf, 0.01)
        is_impulse      = (pred_conf >= NORMAL_MIN_CONFIDENCE) & \
                          (strength_ratio >= NORMAL_STRENGTH_RATIO)
        is_high_conv    = pred_conf >= HIGH_CONVICTION_THRESHOLD

        has_signal   = ~is_inert & (is_impulse | is_high_conv)
        signal_int   = np.where(buy_dominant, 1, -1)
        signal_int   = np.where(has_signal, signal_int, 0)

        # ── Tendencia macro para BOUNTY (simplificada: usando h1/h4 RSI vs 50)
        h1_bull = df['h1_rsi_14'].values > 50 if 'h1_rsi_14' in df.columns else np.zeros(len(df), dtype=bool)
        h4_bull = df['h4_rsi_14'].values > 50 if 'h4_rsi_14' in df.columns else np.zeros(len(df), dtype=bool)
        rsi_bull = df['rsi_14'].values > 50

        # Alineación: para BUY → todos bullish; para SELL → todos bearish
        trends_up   = rsi_bull & h1_bull & h4_bull
        trends_down = ~rsi_bull & ~h1_bull & ~h4_bull
        trend_aligned = np.where(buy_dominant, trends_up, trends_down)

        # ATR para R/R provisional (se recalcula correctamente en la simulación)
        atr = df['atr_14'].values if 'atr_14' in df.columns else df['close'].values * 0.01
        sl_dist = atr * NORMAL_ATR_SL
        tp_dist = atr * NORMAL_ATR_TP
        rr_prov = tp_dist / np.maximum(sl_dist, 1e-9)

        is_bounty = (
            has_signal &
            (pred_conf >= BOUNTY_CONFIDENCE_THRESHOLD) &
            trend_aligned &
            (rr_prov >= BOUNTY_MIN_RR_RATIO)
        )

        result = pd.DataFrame({
            'signal_int':  signal_int,
            'confidence':  pred_conf,
            'is_bounty':   is_bounty,
        }, index=df.index)

        return result

    async def run_symbol(
        self,
        symbol: str,
        min_confidence: float = NORMAL_MIN_CONFIDENCE,
        limit: int = 50000,
    ) -> list:
        """Ejecuta el backtest completo para un símbolo."""
        print(f"\n[{symbol}] Cargando features...", end='', flush=True)

        df = await self.feature_engineer.get_master_dataframe(symbol, '5m', limit=limit)

        if df.empty or len(df) < 200:
            print(f" ⚠️ Datos insuficientes ({len(df)} velas)")
            return []

        print(f" {len(df):,} velas", flush=True)

        # ── Predicción batch sobre todas las filas
        signals = self._batch_predict(df)

        # Filtro de confianza mínima solicitada
        active_mask = (signals['signal_int'] != 0) & \
                      (signals['confidence'] >= min_confidence)
        signal_rows = signals[active_mask]

        if signal_rows.empty:
            print(f"  → Sin señales con confianza ≥ {min_confidence:.0%}")
            return []

        print(f"  → {len(signal_rows):,} señales generadas. Simulando...", flush=True)

        # Arrays numpy para forward-simulation rápida
        close_arr = df['close'].values
        high_arr  = df['high'].values
        low_arr   = df['low'].values
        atr_arr   = df['atr_14'].values if 'atr_14' in df.columns \
                    else close_arr * 0.01
        times     = df.index

        MAX_CANDLES = 288   # 24h en velas de 5m

        trades = []
        df_positions = list(df.index)

        for ts, row in signal_rows.iterrows():
            i = df_positions.index(ts)

            # Asegurar que hay velas por delante para simular
            if i >= len(close_arr) - 2:
                continue

            direction  = int(row['signal_int'])  # 1=BUY, -1=SELL
            confidence = float(row['confidence'])
            entry      = close_arr[i]
            atr        = atr_arr[i]

            if direction == 1:   # BUY
                sl = entry - atr * NORMAL_ATR_SL
                tp = entry + atr * NORMAL_ATR_TP
            else:                # SELL
                sl = entry + atr * NORMAL_ATR_SL
                tp = entry - atr * NORMAL_ATR_TP

            sl_dist = abs(entry - sl)
            tp_dist = abs(entry - tp)
            rr_ratio = tp_dist / sl_dist if sl_dist > 0 else 0.0

            # ── Forward-simulation vectorizada con numpy (50-100x más rápida)
            end_idx    = min(i + MAX_CANDLES + 1, len(high_arr))
            fut_high   = high_arr[i + 1:end_idx]
            fut_low    = low_arr[i + 1:end_idx]
            result     = 'TIMEOUT'
            exit_price = close_arr[min(i + MAX_CANDLES, len(close_arr) - 1)]
            candles_held = len(fut_high)

            if direction == 1:  # BUY
                tp_hits = np.where(fut_high >= tp)[0]
                sl_hits = np.where(fut_low  <= sl)[0]
            else:               # SELL
                tp_hits = np.where(fut_low  <= tp)[0]
                sl_hits = np.where(fut_high >= sl)[0]

            first_tp = tp_hits[0] if len(tp_hits) > 0 else MAX_CANDLES + 1
            first_sl = sl_hits[0] if len(sl_hits) > 0 else MAX_CANDLES + 1

            if first_tp <= first_sl and first_tp <= MAX_CANDLES:
                result       = 'WIN'
                exit_price   = tp
                candles_held = int(first_tp) + 1
            elif first_sl < first_tp and first_sl <= MAX_CANDLES:
                result       = 'LOSS'
                exit_price   = sl
                candles_held = int(first_sl) + 1

            # PnL bruto como % del precio de entrada
            if direction == 1:
                pnl_gross = (exit_price - entry) / entry * 100
            else:
                pnl_gross = (entry - exit_price) / entry * 100

            # ── Comisiones reales de Binance Futures
            # Entrada:   siempre market (taker) = 0.04%
            # TP exit:   orden límite (maker)   = 0.02%
            # SL exit:   orden market (taker)   = 0.04%
            # Funding:   ~0.01% cada 8h — estimado por tiempo en posición
            TAKER = 0.04
            MAKER = 0.02
            if result == 'WIN':
                fee_pct = TAKER + MAKER          # 0.06%
            else:
                fee_pct = TAKER + TAKER          # 0.08%

            # Funding estimado (solo si posición dura más de 8h)
            hours_held = candles_held * 5 / 60
            funding_periods = int(hours_held / 8)
            funding_cost = funding_periods * 0.01  # 0.01% cada 8h

            total_fees = fee_pct + funding_cost
            pnl_net = pnl_gross - total_fees

            trades.append({
                'symbol':        symbol,
                'timestamp':     ts,
                'signal':        'BUY' if direction == 1 else 'SELL',
                'confidence':    round(confidence, 4),
                'entry':         round(entry, 6),
                'sl':            round(sl, 6),
                'tp':            round(tp, 6),
                'exit':          round(exit_price, 6),
                'rr_ratio':      round(rr_ratio, 2),
                'result':        result,
                'pnl_gross_pct': round(pnl_gross, 4),
                'fees_pct':      round(total_fees, 4),
                'pnl_pct':       round(pnl_net, 4),   # neto (lo real)
                'candles_held':  candles_held,
                'hours_held':    round(hours_held, 1),
                'is_bounty':     bool(row['is_bounty']),
            })

        return trades

    async def run_all(
        self,
        symbols: list,
        min_confidence: float = NORMAL_MIN_CONFIDENCE,
        limit: int = 50000,
        save_path: str = None,
    ) -> list:
        """Ejecuta el backtest para todos los símbolos y muestra el reporte."""
        await self.db.connect()
        all_trades = []

        for symbol in symbols:
            trades = await self.run_symbol(symbol, min_confidence, limit=limit)
            all_trades.extend(trades)

        await self.db.close()

        if not all_trades:
            print("\n⚠️ No se generaron señales en el período analizado.")
            return []

        self._print_report(all_trades)

        if save_path:
            pd.DataFrame(all_trades).to_csv(save_path, index=False)
            print(f"\n💾 Resultados guardados en: {save_path}")

        return all_trades

    def _print_report(self, all_trades: list):
        """Imprime el reporte consolidado del backtest."""
        df = pd.DataFrame(all_trades)

        total     = len(df)
        wins      = (df['result'] == 'WIN').sum()
        losses    = (df['result'] == 'LOSS').sum()
        timeouts  = (df['result'] == 'TIMEOUT').sum()
        win_rate  = wins / total * 100

        avg_win_pct   = df[df['result'] == 'WIN']['pnl_pct'].mean() if wins > 0 else 0
        avg_loss_pct  = df[df['result'] == 'LOSS']['pnl_pct'].mean() if losses > 0 else 0
        total_pnl_net = df['pnl_pct'].sum()
        total_fees    = df['fees_pct'].sum() if 'fees_pct' in df.columns else 0
        total_pnl_gross = df['pnl_gross_pct'].sum() if 'pnl_gross_pct' in df.columns else total_pnl_net
        avg_hold_h    = df['hours_held'].mean() if 'hours_held' in df.columns else 0

        gross_wins   = df[df['result'] == 'WIN']['pnl_pct'].sum()
        gross_losses = abs(df[df['result'] == 'LOSS']['pnl_pct'].sum())
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else float('inf')

        print("\n" + "=" * 62)
        print("  SYSMHO — REPORTE BACKTEST HISTÓRICO (con fees reales)")
        print(f"  Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 62)
        print(f"\n  Total señales   : {total:,}")
        print(f"  Ganadas  (WIN)  : {wins:,}  ({win_rate:.1f}%)")
        print(f"  Perdidas (LOSS) : {losses:,}  ({100-win_rate-timeouts/total*100:.1f}%)")
        print(f"  Timeout  (24h)  : {timeouts:,}")
        print(f"  Hold promedio   : {avg_hold_h:.1f}h")
        print(f"\n  ── PnL BRUTO (sin fees)")
        print(f"  Ganancia media  : +{df[df['result']=='WIN']['pnl_gross_pct'].mean():.3f}%" if 'pnl_gross_pct' in df.columns else "")
        print(f"  PnL acumulado   : {'+' if total_pnl_gross >= 0 else ''}{total_pnl_gross:.2f}%")
        print(f"\n  ── PnL NETO (con fees Binance: 0.04% taker / 0.02% maker)")
        print(f"  Ganancia media  : +{avg_win_pct:.3f}%")
        print(f"  Pérdida media   :  {avg_loss_pct:.3f}%")
        print(f"  Total fees      : -{total_fees:.2f}%")
        print(f"  PnL acumulado   : {'+' if total_pnl_net >= 0 else ''}{total_pnl_net:.2f}%")
        print(f"  Profit Factor   : {profit_factor:.2f}x")
        print(f"  R/R promedio    : {df['rr_ratio'].mean():.2f}")

        # ── BOUNTY stats
        b_df = df[df['is_bounty']]
        if len(b_df) > 0:
            b_wins = (b_df['result'] == 'WIN').sum()
            b_wr   = b_wins / len(b_df) * 100
            b_pnl  = b_df['pnl_pct'].sum()
            print(f"\n  ─── SEÑALES BOUNTY (alta convicción ≥{BOUNTY_CONFIDENCE_THRESHOLD:.0%})")
            print(f"  Total   : {len(b_df)}")
            print(f"  Win Rate: {b_wr:.1f}%")
            print(f"  PnL     : {'+' if b_pnl >= 0 else ''}{b_pnl:.2f}%")

        # ── Por símbolo
        print("\n" + "-" * 62)
        print(f"  {'SÍMBOLO':<12} {'SEÑALES':>7} {'WIN%':>7} {'PnL%':>10} {'PF':>8} {'BOUNTY':>8}")
        print("-" * 62)

        for symbol in sorted(df['symbol'].unique()):
            s     = df[df['symbol'] == symbol]
            s_tot = len(s)
            s_w   = (s['result'] == 'WIN').sum()
            s_wr  = s_w / s_tot * 100
            s_pnl = s['pnl_pct'].sum()
            s_gw  = s[s['result'] == 'WIN']['pnl_pct'].sum()
            s_gl  = abs(s[s['result'] == 'LOSS']['pnl_pct'].sum())
            s_pf  = s_gw / s_gl if s_gl > 0 else float('inf')
            s_b   = s['is_bounty'].sum()
            pf_s  = f"{s_pf:.2f}" if s_pf != float('inf') else "  ∞"
            print(f"  {symbol:<12} {s_tot:>7,} {s_wr:>6.1f}% {s_pnl:>+9.2f}% {pf_s:>8} {s_b:>8}")

        print("=" * 62)

        # ── Señal de calidad
        if win_rate >= 55 and profit_factor >= 1.5:
            print("\n  ✅ Sistema rentable — listo para testnet con atención.")
        elif win_rate >= 50 and profit_factor >= 1.2:
            print("\n  ⚠️  Sistema marginal — considera ajustar umbrales.")
        else:
            print("\n  ❌ Sistema no rentable en este período — no operar aún.")

        print()


async def _main():
    parser = argparse.ArgumentParser(
        description="SysMho Backtest — Simulación histórica con datos de PostgreSQL"
    )
    parser.add_argument(
        '--symbol', type=str, default=None,
        help="Símbolo a evaluar (ej: BTC/USDT). Sin valor = todos."
    )
    parser.add_argument(
        '--min-confidence', type=float, default=NORMAL_MIN_CONFIDENCE,
        help=f"Confianza mínima para incluir una señal (default: {NORMAL_MIN_CONFIDENCE})"
    )
    parser.add_argument(
        '--limit', type=int, default=50000,
        help="Número máximo de velas a analizar por símbolo (default: 50000 ≈ 6 meses)"
    )
    parser.add_argument(
        '--save', type=str, default=None,
        help="Ruta CSV para exportar los resultados (ej: backtest_results.csv)"
    )
    args = parser.parse_args()

    symbols = [args.symbol] if args.symbol else SYMBOLS
    meses = round(args.limit * 5 / 60 / 24 / 30, 1)

    print("=" * 62)
    print("  SYSMHO — BACKTEST HISTÓRICO")
    print(f"  Activos    : {', '.join(symbols)}")
    print(f"  Confianza  : ≥ {args.min_confidence:.0%}")
    print(f"  Período    : últimas {args.limit:,} velas ≈ {meses} meses")
    print("=" * 62)

    engine = BacktestEngine()
    await engine.run_all(
        symbols,
        min_confidence=args.min_confidence,
        limit=args.limit,
        save_path=args.save,
    )


if __name__ == "__main__":
    asyncio.run(_main())
