"""
SysMho — Descargador Masivo de Historia (Backfill).

Recupera datos históricos desde un año específico.
Opera contra Binance Mainnet pública Futures (no requiere API keys).
Usa el mercado Futures para coherencia con el sistema operativo.
"""

import argparse
import asyncio
from datetime import datetime, timezone

import ccxt.async_support as ccxt

from src.database.repository import DatabaseRepository


async def backfill_history(
    symbol: str = 'BTC/USDT', timeframe: str = '1h', start_year: int = 2020
) -> None:
    """
    Descarga todo el historial disponible para un par y timeframe dado.

    Args:
        symbol: Par a descargar (ej. 'BTC/USDT').
        timeframe: Temporalidad (ej. '1h', '5m').
        start_year: Año de inicio para la búsqueda hacia adelante.
    """
    print(f"\n🚀 [INICIANDO FASE 9] Descargador Masivo de Historia: {symbol}")
    print(f"📊 Objetivo: Toda la data desde el 1 Enero {start_year}.")

    # MAINNET: Binance Real pública porque Testnet no tiene historia vieja.
    # Usamos Futures para coherencia con el mercado donde opera SysMho.
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })

    db = DatabaseRepository()
    await db.connect()

    start_dt = datetime(start_year, 1, 1, tzinfo=timezone.utc)
    since = int(start_dt.timestamp() * 1000)

    now = exchange.milliseconds()
    limit = 1000  # Máximo por petición
    total_downloaded = 0

    print("\n⏳ Conectando al Servidor de Binance...")

    while since < now:
        try:
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, since, limit)

            if not ohlcv or len(ohlcv) == 0:
                print("🏁 No hay más datos o se alcanzó el presente.")
                break

            records = []
            for row in ohlcv:
                timestamp_ms = row[0]
                open_time = datetime.fromtimestamp(
                    timestamp_ms / 1000.0, tz=timezone.utc
                )

                records.append((
                    symbol,
                    timeframe,
                    open_time,
                    float(row[1]),  # Open
                    float(row[2]),  # High
                    float(row[3]),  # Low
                    float(row[4]),  # Close
                    float(row[5])   # Volume
                ))

            # Guardamos el lote (Ignora automáticamente duplicados)
            await db.insert_market_data_batch(records)
            total_downloaded += len(records)

            last_candle_ms = ohlcv[-1][0]
            since = last_candle_ms + 1
            last_date = datetime.fromtimestamp(
                last_candle_ms / 1000.0, tz=timezone.utc
            ).strftime('%Y-%m-%d %H:%M:%S')

            print(f"✅ Lote guardado. Avance: {last_date} | "
                  f"Total: {total_downloaded} velas")

            await asyncio.sleep(exchange.rateLimit / 1000)

            # --- PAUSA EXTRA ANTI-SPAM ---
            if total_downloaded % 10000 == 0:
                print("💤 Pausa respiratoria de 2s para evitar baneos...")
                await asyncio.sleep(2)

        except ccxt.NetworkError as e:
            print(f"⚠️ Error de red temporal: {e}. Reintentando en 3s...")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"❌ Error crítico: {e}")
            break

    count = await db.get_market_data_count(symbol, timeframe)
    print("\n" + "=" * 50)
    print("🏆 DESCARGA HISTÓRICA COMPLETADA")
    print(f"📈 Total de velas almacenadas en PostgreSQL: {count}")
    print("=" * 50 + "\n")

    await exchange.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Descargador SysMho')
    parser.add_argument('--symbol', type=str, default='BTC/USDT',
                        help='Símbolo (ej: BTC/USDT)')
    parser.add_argument('--timeframe', type=str, default='1h',
                        help='Temporalidad (ej: 1h, 5m)')
    parser.add_argument('--year', type=int, default=2020,
                        help='Año inicial')

    args = parser.parse_args()

    try:
        asyncio.run(backfill_history(
            symbol=args.symbol,
            timeframe=args.timeframe,
            start_year=args.year
        ))
    except KeyboardInterrupt:
        print("\nDescarga interrumpida manualmente.")
