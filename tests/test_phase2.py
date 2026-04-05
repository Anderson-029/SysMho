"""
SysMho — Tests de Validación: Fase 2 (Capa de Datos).

Estos tests FALLARÁN hasta que la Fase 2 esté implementada.
Son la definición exacta de lo que debe quedar correcto al terminar la fase.
"""

import pytest


# ================================================================
# 1. Backfill usa mercado Futures, no Spot
# ================================================================

def test_backfill_uses_futures_market():
    """
    backfill.py debe usar 'future' para ser coherente con el sistema.
    El sistema opera en Binance Futures — el historial debe provenir del mismo mercado.
    """
    with open("src/collector/backfill.py", "r", encoding="utf-8") as f:
        content = f.read()

    assert "'spot'" not in content, (
        "backfill.py usa 'defaultType': 'spot'. "
        "El sistema opera en Futures — cambiar a 'defaultType': 'future'."
    )
    assert "'future'" in content, (
        "backfill.py no contiene 'future'. "
        "Debe usar 'defaultType': 'future' en la configuración de CCXT."
    )


# ================================================================
# 2. MarketDataCollector respeta BINANCE_TESTNET
# ================================================================

def test_market_data_collector_respects_testnet_env():
    """
    market_data.py fue eliminado en cleanup (era código huérfano que duplicaba
    backfill.py). El control de testnet queda únicamente en trader.py (TradeExecutor).
    """
    import pytest
    pytest.skip("market_data.py eliminado — era código muerto (duplicaba backfill.py)")


# ================================================================
# 3. Leverage real, no hardcodeado 1.0
# ================================================================

def test_leverage_not_hardcoded_in_execute_trade():
    """
    execute_trade debe registrar el leverage real de la posición,
    no pasar 1.0 como literal hardcodeado a _log_trade.
    """
    with open("src/executor/trader.py", "r", encoding="utf-8") as f:
        content = f.read()

    assert "1.0, order['id']" not in content, (
        "execute_trade pasa 1.0 hardcodeado como leverage a _log_trade. "
        "Debe obtener el leverage real desde Binance tras abrir la posición."
    )


# ================================================================
# 4. signal_type en risk_log acepta más de 10 caracteres (DB)
# ================================================================

@pytest.mark.asyncio
async def test_signal_type_column_accepts_long_values(db_pool):
    """
    risk_log.signal_type debe aceptar valores de más de 10 caracteres.
    'EXPLORACIÓN' tiene 11 chars — fallará con VARCHAR(10) actual.
    """
    async with db_pool.acquire() as conn:
        try:
            await conn.execute("""
                INSERT INTO risk_log (signal_type, symbol, reason, approved, risk_score)
                VALUES ($1, $2, $3, $4, $5)
            """, 'EXPLORACIÓN', 'BTC/USDT', '__test_phase2__', False, 0.0)

            # Limpiar el registro de prueba
            await conn.execute(
                "DELETE FROM risk_log WHERE reason = '__test_phase2__'"
            )

        except Exception as e:
            pytest.fail(
                f"risk_log.signal_type VARCHAR(10) rechaza 'EXPLORACIÓN' (11 chars): {e}\n"
                "Solución: ALTER TABLE risk_log ALTER COLUMN signal_type TYPE VARCHAR(20)"
            )


# ================================================================
# 5. atr_14 se inserta con los datos de mercado (DB)
# ================================================================

@pytest.mark.asyncio
async def test_atr14_populated_in_market_data(db_pool):
    """
    Después de insertar datos de mercado, atr_14 debe estar calculado
    en al menos el 90% de los registros (los primeros 14 no pueden tenerlo).
    """
    from src.database.repository import DatabaseRepository

    repo = DatabaseRepository()
    repo.pool = db_pool
    await repo.backfill_atr_14_all()

    async with db_pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM market_data WHERE timeframe = '5m'"
        )

        if total == 0:
            pytest.skip(
                "No hay datos en market_data (timeframe=5m). "
                "Ejecutar backfill primero y luego repetir el test."
            )

        # ATR-14 requiere al menos 14 velas consecutivas por (symbol); sin eso atr_14 queda NULL.
        eligible = await conn.fetch(
            """
            SELECT symbol, COUNT(*) AS n
            FROM market_data
            WHERE timeframe = '5m'
            GROUP BY symbol
            HAVING COUNT(*) >= 14
            """
        )
        if not eligible:
            pytest.skip(
                "Ningún símbolo tiene ≥14 velas en 5m; no se puede validar atr_14. "
                "Cargar más histórico por símbolo."
            )

        for row in eligible:
            symbol = row["symbol"]
            n = row["n"]
            null_count = await conn.fetchval(
                "SELECT COUNT(*) FROM market_data "
                "WHERE timeframe = '5m' AND symbol = $1 AND atr_14 IS NULL",
                symbol,
            )
            null_ratio = null_count / n
            assert null_ratio < 0.10, (
                f"{symbol}: {null_count}/{n} registros tienen atr_14 = NULL ({null_ratio:.0%}).\n"
                "El colector debe calcular ATR antes de insertar y guardarlo en la columna atr_14."
            )
