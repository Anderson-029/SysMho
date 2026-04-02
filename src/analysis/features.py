"""
SysMho — Ingeniería de Características (Feature Engineering).

Extrae datos, calcula indicadores, inyecta contexto macro (1h, 4h)
y sanitiza los datos para entrenar o alimentar a la IA.
"""

from typing import Optional

import numpy as np
import pandas as pd

from src.analysis.indicators import TechnicalIndicators
from src.constants import MACRO_TIMEFRAMES, SYMBOLS
from src.database.repository import DatabaseRepository


class FeatureEngineer:
    """Clase principal para la construcción del dataset de IA."""

    def __init__(self, db: Optional[DatabaseRepository] = None) -> None:
        """Inicializa recibiendo o creando el repositorio."""
        self.db = db if db else DatabaseRepository()

    async def get_master_dataframe(
        self, symbol: str, timeframe: str, limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Extrae datos, inyecta indicadores y unifica contextos macro.

        Si el timeframe es 5m, inyecta contexto de 1h y 4h.
        """
        await self.db.connect()

        # 1. Obtención de datos primarios
        df = await self._fetch_data(symbol, timeframe, limit)
        if df.empty:
            return df

        # PASO 1: Inyectar indicadores técnicos primarios
        df = TechnicalIndicators.add_all_indicators(df)

        # 2. Inyección Multi-Temporal (Solo en 5m para contexto macro)
        if timeframe == '5m':
            df = await self._inject_macro_context(df, symbol, limit)

        # PASO 2: Limpieza Quirúrgica de Nulos (EMA gap, etc)
        df.dropna(inplace=True)

        # PASO 3: Feature Engineering Dinámico
        df['pct_change'] = df['close'].pct_change()
        df['vol_change'] = df['volume'].pct_change()

        # PASO 3.3: Normalización de indicadores absolutos
        # Convierte precios/distancias en porcentajes del precio para eliminar
        # el sesgo de escala entre activos (BTC $60k vs POL $0.5)
        df['atr_pct'] = (df['atr_14'] / df['close']) * 100
        df['ema_21_dist'] = (df['close'] - df['ema_21']) / df['close'] * 100
        df['ema_200_dist'] = (df['close'] - df['ema_200']) / df['close'] * 100
        df['vwap_dist'] = (df['close'] - df['vwap']) / df['close'] * 100
        df['macd_diff_pct'] = (df['macd_diff'] / df['close']) * 100

        # PASO 3.5: Inyección Institucional (Sentimiento y Liquidez)
        sentiment = await self.db.get_sentiment(symbol)
        if sentiment:
            df['funding_rate'] = sentiment['funding_rate']
            df['obi_20'] = sentiment['obi_20']
        else:
            df['funding_rate'] = 0.0
            df['obi_20'] = 0.0

        # PASO 3.8: Matemática de Enjambre (Swarm Intelligence)
        # Se excluye el símbolo actual para evitar que se evalúe a sí mismo
        swarm_df = await self._calculate_historical_swarm(limit, exclude_symbol=symbol)
        if not swarm_df.empty:
            df = df.join(swarm_df, how='left')
            df['swarm_rsi_avg'] = df['swarm_rsi_avg'].fillna(50.0)
            df['swarm_macd_avg'] = df['swarm_macd_avg'].fillna(0.0)
            df['swarm_bull_ratio'] = df['swarm_bull_ratio'].fillna(0.5)
        else:
            df['swarm_rsi_avg'] = 50.0
            df['swarm_macd_avg'] = 0.0
            df['swarm_bull_ratio'] = 0.5

        # PASO 3.9: Normalización de features macro (1h y 4h)
        # Los indicadores macro se inyectan como precios absolutos; se normalizan
        # aquí usando el close del 5m como referencia de escala
        for prefix in ['h1', 'h4']:
            atr_col = f'{prefix}_atr_14'
            macd_diff_col = f'{prefix}_macd_diff'
            if atr_col in df.columns:
                df[f'{prefix}_atr_pct'] = (df[atr_col] / df['close']) * 100
            else:
                df[f'{prefix}_atr_pct'] = 0.0
            if macd_diff_col in df.columns:
                df[f'{prefix}_macd_diff_pct'] = (df[macd_diff_col] / df['close']) * 100
            else:
                df[f'{prefix}_macd_diff_pct'] = 0.0

        # PASO 4: Sanitización Extrema anti-XGBoost Crash
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df.dropna(inplace=True)

        return df

    async def _fetch_data(
        self, symbol: str, timeframe: str, limit: Optional[int] = None
    ) -> pd.DataFrame:
        """Descarga OHLCV de la DB con límite opcional."""
        query = f'''
            SELECT open_time, open, high, low, close, volume 
            FROM market_data 
            WHERE symbol = $1 AND timeframe = $2
            ORDER BY open_time DESC
            {f"LIMIT {limit}" if limit else ""};
        '''
        async with self.db.pool.acquire() as conn:
            records = await conn.fetch(query, symbol, timeframe)

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(
            records,
            columns=['open_time', 'open', 'high', 'low', 'close', 'volume']
        )
        # Invertir porque pedimos DESC para el LIMIT
        df = df.iloc[::-1].reset_index(drop=True)

        # Asegurar index datetime para merge_asof
        df['open_time'] = pd.to_datetime(df['open_time'])
        df.set_index('open_time', inplace=True)

        for col in df.columns:
            df[col] = df[col].astype(float)

        return df

    async def _inject_macro_context(
        self, df_5m: pd.DataFrame, symbol: str, limit: Optional[int] = None
    ) -> pd.DataFrame:
        """Inyecta contexto de temporalidades mayores sin sesgo."""
        df_combined = df_5m.copy()

        for tf in MACRO_TIMEFRAMES:
            df_tf = await self._fetch_data(symbol, tf, limit)
            if df_tf.empty:
                print(f"⚠️ [Macro] Sin datos de {tf} para {symbol}. Saltando.")
                continue

            # Calcular indicadores en el timeframe macro
            df_tf = TechnicalIndicators.add_all_indicators(df_tf)

            # Prefijo para columnas macro (h1_ o h4_)
            prefix = tf.replace('1h', 'h1').replace('4h', 'h4')

            # Renombrar columnas (excepto OHLCV)
            base_cols = ['open', 'high', 'low', 'close', 'volume']
            cols_to_rename = [c for c in df_tf.columns if c not in base_cols]
            df_tf.rename(
                columns={c: f"{prefix}_{c}" for c in cols_to_rename},
                inplace=True
            )

            # Filtrar solo indicadores
            macro_features = [f"{prefix}_{c}" for c in cols_to_rename]
            df_tf_clean = df_tf[macro_features]

            # Merge ASOF
            df_combined.sort_index(inplace=True)
            df_tf_clean.sort_index(inplace=True)

            df_combined = pd.merge_asof(
                df_combined,
                df_tf_clean,
                left_index=True,
                right_index=True,
                direction='backward'
            )

        return df_combined

    async def _calculate_historical_swarm(
        self, limit: Optional[int] = None, exclude_symbol: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Matemática de Enjambre: Calcula la temperatura global del ecosistema
        promediando los indicadores técnicos de todo el portafolio.

        Usa una sola query con ANY($1) en lugar de 10 queries separadas (una por símbolo).
        El parámetro exclude_symbol evita que el símbolo evaluado se incluya en su
        propio enjambre (sesgo de auto-evaluación).
        """
        safe_limit = (limit + 50) if limit else 300

        # Excluir el símbolo actual para que no se evalúe a sí mismo
        symbols_to_query = [s for s in SYMBOLS if s != exclude_symbol]

        # Una sola query para todos los símbolos del enjambre
        query = '''
            SELECT symbol, open_time, open, high, low, close, volume
            FROM (
                SELECT symbol, open_time, open, high, low, close, volume,
                       ROW_NUMBER() OVER (
                           PARTITION BY symbol ORDER BY open_time DESC
                       ) AS rn
                FROM market_data
                WHERE symbol = ANY($1) AND timeframe = '5m'
            ) sub
            WHERE rn <= $2
            ORDER BY symbol, open_time ASC
        '''
        async with self.db.pool.acquire() as conn:
            records = await conn.fetch(query, symbols_to_query, safe_limit)

        if not records:
            return pd.DataFrame()

        # Agrupar por símbolo y calcular indicadores
        from collections import defaultdict
        symbol_rows = defaultdict(list)
        for r in records:
            symbol_rows[r['symbol']].append(r)

        all_dfs = []
        for sym, rows in symbol_rows.items():
            df = pd.DataFrame(rows, columns=[
                'symbol', 'open_time', 'open', 'high', 'low', 'close', 'volume'
            ])
            df = df.drop('symbol', axis=1)
            df['open_time'] = pd.to_datetime(df['open_time'])
            df.set_index('open_time', inplace=True)
            for col in df.columns:
                df[col] = df[col].astype(float)

            df = TechnicalIndicators.add_all_indicators(df)
            required = {'rsi_14', 'macd', 'ema_21', 'close'}
            if required.issubset(df.columns):
                # swarm_bull_ratio: 1 si el precio está por encima de EMA21 (tendencia alcista)
                is_bull = (df['close'] > df['ema_21']).astype(float)
                df = df[['rsi_14', 'macd']].copy()
                df[f'bull_{sym}'] = is_bull
                df.rename(
                    columns={'rsi_14': f'rsi_{sym}', 'macd': f'macd_{sym}'},
                    inplace=True
                )
                all_dfs.append(df)

        if not all_dfs:
            return pd.DataFrame()

        # Unir todos por índice (open_time)
        swarm_df = pd.concat(all_dfs, axis=1)

        # Calcular medias del enjambre
        rsi_cols = [c for c in swarm_df.columns if c.startswith('rsi_')]
        macd_cols = [c for c in swarm_df.columns if c.startswith('macd_')]
        bull_cols = [c for c in swarm_df.columns if c.startswith('bull_')]

        final_swarm = pd.DataFrame(index=swarm_df.index)
        final_swarm['swarm_rsi_avg'] = swarm_df[rsi_cols].mean(axis=1)
        final_swarm['swarm_macd_avg'] = swarm_df[macd_cols].mean(axis=1)
        final_swarm['swarm_bull_ratio'] = swarm_df[bull_cols].mean(axis=1)

        # Rellenar posibles baches asíncronos
        final_swarm.ffill(inplace=True)

        # LAG FIX: Desplazar 1 período para evitar sesgo hacia el futuro.
        # En el momento T, el swarm refleja el estado en T-1 (siempre conocido).
        final_swarm = final_swarm.shift(1)

        final_swarm.fillna(
            {'swarm_rsi_avg': 50.0, 'swarm_macd_avg': 0.0, 'swarm_bull_ratio': 0.5},
            inplace=True
        )

        return final_swarm
