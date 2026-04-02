"""
SysMho — Indicadores Técnicos.

Calcula indicadores técnicos sobre un DataFrame de Pandas (OHLCV).
Se encarga de inyectar las nuevas columnas matemáticas a los precios en crudo.
"""

import pandas as pd
import ta


class TechnicalIndicators:
    """Clase estática para cálculo de indicadores matemáticos."""

    @staticmethod
    def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula y añade todos los indicadores técnicos base usando 'ta'.

        Args:
            df: DataFrame con columnas OHLCV estándar.

        Returns:
            DataFrame con las nuevas columnas calculadas.
        """
        df = df.copy()

        # 1. RSI (Relative Strength Index)
        df['rsi_14'] = ta.momentum.rsi(df['close'], window=14)

        # 2. MACD (Moving Average Convergence Divergence)
        macd = ta.trend.MACD(df['close'])
        df['macd'] = macd.macd()
        df['macd_diff'] = macd.macd_diff()

        # 3. Bollinger Bands
        bollinger = ta.volatility.BollingerBands(
            df['close'], window=20, window_dev=2
        )
        # Posición del precio respecto a las bandas (0 a 1)
        df['bb_pband'] = bollinger.bollinger_pband()

        # 4. Medias Móviles Exponenciales (EMAs usadas como features o intermedias)
        df['ema_21'] = ta.trend.ema_indicator(df['close'], window=21)
        df['ema_200'] = ta.trend.ema_indicator(df['close'], window=200)

        # 5. ATR (Average True Range)
        df['atr_14'] = ta.volatility.average_true_range(
            df['high'], df['low'], df['close'], window=14
        )

        # 6. VWAP (Volume Weighted Average Price)
        vwap = ta.volume.VolumeWeightedAveragePrice(
            high=df['high'], low=df['low'], close=df['close'],
            volume=df['volume'], window=14
        )
        df['vwap'] = vwap.volume_weighted_average_price()

        # 7. ADX (Average Directional Index)
        adx = ta.trend.ADXIndicator(
            high=df['high'], low=df['low'], close=df['close'], window=14
        )
        df['adx'] = adx.adx()
        df['adx_pos'] = adx.adx_pos()  # Fuerza alcista

        # 8. StochRSI (Stochastic RSI)
        stoch_rsi = ta.momentum.StochRSIIndicator(
            close=df['close'], window=14, smooth1=3, smooth2=3
        )
        df['stoch_rsi_k'] = stoch_rsi.stochrsi_k()

        return df
