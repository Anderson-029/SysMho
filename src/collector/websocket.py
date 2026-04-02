"""
SysMho — Colector de WebSocket.

Se conecta a la API en tiempo real de Binance Futures usando CCXT Pro.
Mantiene la base de datos sincronizada con las últimas velas (OHLCV)
de los activos configurados.

ARQUITECTURA DE CONEXIÓN:
  - Datos de mercado (OHLCV, Funding Rate, Order Book) → SIEMPRE Binance REAL.
    Son endpoints públicos que no requieren autenticación ni modo sandbox.
  - Ejecución de órdenes → TradeExecutor (trader.py), que sí respeta
    BINANCE_TESTNET para operar con dinero real o simulado.

Esto garantiza que las predicciones de la IA siempre se basen en
precios reales del mercado, independientemente del modo de operación.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

import ccxt.pro as ccxt_pro

from src.database.repository import DatabaseRepository


class BinanceWebSocket:
    """Clase para manejar las conexiones en vivo usando CCXT Pro."""

    def __init__(
        self, use_auth: bool = True, db: Optional[DatabaseRepository] = None
    ) -> None:
        """
        Inicializa el cliente de WebSocket apuntando siempre a Binance REAL.

        Los datos de mercado son públicos — no se requiere autenticación
        ni modo sandbox. El parámetro use_auth se mantiene por compatibilidad
        pero no activa sandbox (eso es responsabilidad del TradeExecutor).

        Args:
            use_auth: Reservado para compatibilidad. No activa sandbox.
            db: Instancia opcional de DatabaseRepository para reutilización.
        """
        # Siempre Binance REAL para datos de mercado (endpoints públicos)
        self.exchange = ccxt_pro.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'},
        })

        self.db = db if db else DatabaseRepository()
        self.running: bool = False
        self._started_symbols: set = set()

    async def watch_ohlcv(self, symbol: str, timeframe: str) -> None:
        """
        Loop infinito asíncrono que escucha velas en tiempo real.

        Args:
            symbol: El par a monitorear (ej. 'BTC/USDT').
            timeframe: La temporalidad sugerida (ej. '5m').
        """
        self.running = True
        await self.db.connect()
        print(f"📡 Conectado al stream en vivo de {symbol} ({timeframe})")

        # Lanzar tasks de sentimiento y order book solo una vez por símbolo.
        # watch_ohlcv se llama 3 veces por símbolo (5m, 1h, 4h) — sin este guard
        # se generarían 30 tasks duplicadas para 10 símbolos.
        if symbol not in self._started_symbols:
            self._started_symbols.add(symbol)
            asyncio.create_task(self._keep_sentiment_alive(symbol))
            asyncio.create_task(self._monitor_order_book(symbol))

        while self.running:
            try:
                # Bloquea de forma asíncrona hasta recibir nuevo tick
                ohlcv = await self.exchange.watch_ohlcv(symbol, timeframe)

                # 'ohlcv' contiene el historial reciente, usamos la 'viva'
                latest = ohlcv[-1]
                timestamp_ms = latest[0]
                open_time = datetime.fromtimestamp(
                    timestamp_ms / 1000.0, tz=timezone.utc
                )

                record = (
                    symbol,
                    timeframe,
                    open_time,
                    float(latest[1]),  # Open
                    float(latest[2]),  # High
                    float(latest[3]),  # Low
                    float(latest[4]),  # Close
                    float(latest[5])   # Volume
                )

                # Realizamos Upsert a DB para mantenerla actualizada
                await self.db.upsert_market_data(record)

                # Log optimizado para multitasking (heartbeat visual)
                if symbol == 'BTC/USDT' or datetime.now().second % 40 == 0:
                    print(f"🔄 Tick Vivo [{symbol}] -> Precio: {record[6]} USDT")

            except asyncio.CancelledError:
                print(f"🛑 Stream de {symbol} detenido.")
                break
            except Exception as e:
                print(f"❌ Error en stream {symbol}: {e}")
                # Backoff para reconexión
                await asyncio.sleep(5)

    async def close(self) -> None:
        """Cierre ordenado de recursos compartidos (exchange ccxt)."""
        self.running = False
        try:
            await self.exchange.close()
        except Exception:
            pass

    async def _keep_sentiment_alive(self, symbol: str) -> None:
        """
        Sensor Institucional: Obtiene asíncronamente el Funding Rate 
        y el Open Interest cada 60 segundos usando los endpoints de Futuros.
        """
        while self.running:
            try:
                # 1. Obtener Funding Rate (predictive)
                try:
                    fr_data = await self.exchange.fetch_funding_rate(symbol)
                    funding_rate = float(fr_data.get('fundingRate', 0.0))
                except Exception:
                    funding_rate = 0.0

                # 2. Obtener Open Interest
                try:
                    oi_data = await self.exchange.fetch_open_interest(symbol)
                    open_interest = float(oi_data.get('openInterestValue', 0.0))
                except Exception:
                    open_interest = 0.0
                
                # Guardar métricas institucionales en DB para el predictor
                await self.db.upsert_sentiment(symbol, funding_rate, open_interest)
                
            except Exception as e:
                # Errores en métricas secundarias no tiran el WebSocket
                pass
            
            # Latido del sensor: cada 60 segundos
            await asyncio.sleep(60)

    async def _monitor_order_book(self, symbol: str) -> None:
        """
        Radar de Liquidez: Mantiene un snapshot del Order Book (L2) a 20 niveles
        y calcula el Order Book Imbalance (OBI) para detectar asimetrías de liquidez.
        """
        while self.running:
            try:
                # 1. Obtener L2 Order Book en tiempo real (limit=20)
                orderbook = await self.exchange.watch_order_book(symbol, limit=20)
                
                bids = orderbook.get('bids', [])
                asks = orderbook.get('asks', [])
                
                # 2. Sumar volumen (quantity) en los niveles
                total_bids = sum([bid[1] for bid in bids[:20]]) if bids else 0
                total_asks = sum([ask[1] for ask in asks[:20]]) if asks else 0
                
                # 3. Calcular Order Book Imbalance (OBI) [-1.0 a 1.0]
                if total_bids + total_asks > 0:
                    obi_20 = (total_bids - total_asks) / (total_bids + total_asks)
                else:
                    obi_20 = 0.0
                    
                # 4. Actualizar la BD (sin tocar Funding Rate)
                await self.db.upsert_liquidity_radar(symbol, obi_20)
                
            except Exception as e:
                # Backoff silencioso
                await asyncio.sleep(5)
                
            # Rate limit empírico para no saturar DB (cada 5 segs es suficiente para 5m tf)
            await asyncio.sleep(5)
