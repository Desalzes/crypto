import pandas as pd
import numpy as np

class Indicators:
    @staticmethod
    def calculate_all(df: pd.DataFrame, timeframe: str):
        indicators = {}
        indicators.update(Indicators.calculate_rsi(df))
        indicators.update(Indicators.calculate_macd(df))
        indicators.update(Indicators.calculate_bollinger(df))
        indicators.update(Indicators.calculate_ema(df))
        indicators.update(Indicators.calculate_ichimoku(df))
        indicators.update(Indicators.calculate_atr(df))
        indicators.update(Indicators.calculate_obv(df))
        indicators.update(Indicators.calculate_volume_profile(df))
        return indicators

    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period=14):
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return {'rsi': rsi.iloc[-1]}

    @staticmethod
    def calculate_macd(df: pd.DataFrame):
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        return {
            'macd': macd.iloc[-1],
            'macd_signal': signal.iloc[-1]
        }

    @staticmethod
    def calculate_bollinger(df: pd.DataFrame, period=20):
        sma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        return {
            'bb_upper': upper.iloc[-1],
            'bb_lower': lower.iloc[-1],
            'bb_mid': sma.iloc[-1]
        }

    @staticmethod
    def calculate_ema(df: pd.DataFrame):
        ema_short = df['close'].ewm(span=12).mean()
        ema_long = df['close'].ewm(span=26).mean()
        return {
            'ema_short': ema_short.iloc[-1],
            'ema_long': ema_long.iloc[-1]
        }

    @staticmethod
    def calculate_ichimoku(df: pd.DataFrame):
        high_9 = df['high'].rolling(window=9).max()
        low_9 = df['low'].rolling(window=9).min()
        tenkan_sen = (high_9 + low_9) / 2

        high_26 = df['high'].rolling(window=26).max()
        low_26 = df['low'].rolling(window=26).min()
        kijun_sen = (high_26 + low_26) / 2

        return {
            'tenkan_sen': tenkan_sen.iloc[-1],
            'kijun_sen': kijun_sen.iloc[-1]
        }

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period=14):
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(period).mean()
        return {'atr': atr.iloc[-1]}

    @staticmethod
    def calculate_obv(df: pd.DataFrame):
        obv = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        return {'obv': obv.iloc[-1]}

    @staticmethod
    def calculate_volume_profile(df: pd.DataFrame, price_bins=100):
        # Calculate volume profile using price levels
        price_range = df['close'].max() - df['close'].min()
        bin_size = price_range / price_bins
        
        volume_by_price = {}
        for i in range(price_bins):
            price_level = df['close'].min() + (i * bin_size)
            mask = (df['close'] >= price_level) & (df['close'] < price_level + bin_size)
            volume_by_price[price_level] = df.loc[mask, 'volume'].sum()
        
        # Find the Point of Control (price level with highest volume)
        poc_price = max(volume_by_price.items(), key=lambda x: x[1])[0]
        
        return {
            'volume_profile': volume_by_price,
            'poc_price': poc_price
        }

    @staticmethod
    def calculate_dynamic_stop_loss(df: pd.DataFrame, multiplier=2.0):
        """Calculate dynamic stop loss based on ATR"""
        atr = Indicators.calculate_atr(df)['atr']
        return atr * multiplier
