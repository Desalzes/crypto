import numpy as np
import pandas as pd
import asyncio
import time
from database.db_manager import DatabaseManager
import logging

class ResearchMode:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.timeframes = ['1m', '5m', '15m']
        self.logger = logging.getLogger(__name__)
        
    async def research_pair(self, symbol: str, historical_data: dict):
        tasks = []
        for timeframe, data in historical_data.items():
            if data is not None:
                tasks.append(self.analyze_timeframe(symbol, timeframe, data))
                
        await asyncio.gather(*tasks)
        
    async def analyze_timeframe(self, symbol: str, timeframe: str, data: pd.DataFrame):
        try:
            results = self.backtest_indicators(data, symbol, timeframe)
            self.store_results(results, symbol, timeframe)
        except Exception as e:
            self.logger.error(f"Error analyzing {symbol} {timeframe}: {e}")
    
    def backtest_indicators(self, df: pd.DataFrame, pair: str, timeframe: str):
        results = {}
        
        indicator_tests = {
            'RSI': self.test_rsi,
            'MACD': self.test_macd,
            'BOLLINGER': self.test_bollinger,
            'EMA': self.test_ema,
            'ICHIMOKU': self.test_ichimoku
        }
        
        for indicator, test_func in indicator_tests.items():
            signals = test_func(df)
            results[indicator] = self.calculate_success_rate(signals, df)
            
        return results
        
    def test_rsi(self, df: pd.DataFrame, period=14):
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        signals = pd.Series(index=df.index, dtype=float)
        signals[rsi < 30] = 1  
        signals[rsi > 70] = -1
        return signals.fillna(0)
        
    def test_macd(self, df: pd.DataFrame):
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        
        signals = pd.Series(index=df.index, dtype=float)
        signals[macd > signal] = 1
        signals[macd < signal] = -1
        return signals.fillna(0)
        
    def test_bollinger(self, df: pd.DataFrame, period=20):
        sma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        
        signals = pd.Series(index=df.index, dtype=float)
        signals[df['close'] < lower] = 1
        signals[df['close'] > upper] = -1
        return signals.fillna(0)
        
    def test_ema(self, df: pd.DataFrame):
        ema_short = df['close'].ewm(span=12).mean()
        ema_long = df['close'].ewm(span=26).mean()
        
        signals = pd.Series(index=df.index, dtype=float)
        signals[ema_short > ema_long] = 1
        signals[ema_short < ema_long] = -1
        return signals.fillna(0)
        
    def test_ichimoku(self, df: pd.DataFrame):
        high_9 = df['high'].rolling(window=9).max()
        low_9 = df['low'].rolling(window=9).min()
        tenkan_sen = (high_9 + low_9) / 2
        
        high_26 = df['high'].rolling(window=26).max()
        low_26 = df['low'].rolling(window=26).min()
        kijun_sen = (high_26 + low_26) / 2
        
        signals = pd.Series(index=df.index, dtype=float)
        signals[tenkan_sen > kijun_sen] = 1
        signals[tenkan_sen < kijun_sen] = -1
        return signals.fillna(0)
    
    def store_results(self, results: dict, pair: str, timeframe: str):
        for indicator, (success_rate, total_trades) in results.items():
            self.db.update_indicator_performance(
                pair, timeframe, indicator, success_rate, total_trades
            )
            
    def calculate_success_rate(self, signals: pd.Series, df: pd.DataFrame):
        if len(signals) == 0:
            return 0, 0
            
        future_returns = df['close'].pct_change().shift(-1)
        correct_predictions = ((signals == 1) & (future_returns > 0)) | ((signals == -1) & (future_returns < 0))
        success_rate = correct_predictions.mean()
        total_trades = len(signals[signals != 0])
        
        return float(success_rate), total_trades