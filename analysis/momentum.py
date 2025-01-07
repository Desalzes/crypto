import pandas as pd
import numpy as np

class MomentumAnalyzer:
    @staticmethod
    def calculate_volume_profile(df: pd.DataFrame) -> dict:
        avg_volume = df['volume'].mean()
        current_volume = df['volume'].iloc[-1]
        volume_trend = current_volume / avg_volume
        
        return {
            'volume_ratio': volume_trend,
            'is_high_volume': volume_trend > 1.5,
            'is_low_volume': volume_trend < 0.5
        }
    
    @staticmethod
    def calculate_momentum(df: pd.DataFrame, window: int = 20) -> dict:
        returns = df['close'].pct_change()
        momentum = returns.rolling(window=window).mean()
        volatility = returns.rolling(window=window).std()
        
        # Calculate momentum strength
        z_score = (momentum.iloc[-1] - momentum.mean()) / momentum.std()
        
        return {
            'momentum': momentum.iloc[-1],
            'volatility': volatility.iloc[-1],
            'z_score': z_score,
            'trend_strength': abs(z_score)
        }
    
    @staticmethod
    def analyze_price_levels(df: pd.DataFrame) -> dict:
        recent_high = df['high'].rolling(window=20).max().iloc[-1]
        recent_low = df['low'].rolling(window=20).min().iloc[-1]
        current_price = df['close'].iloc[-1]
        
        # Calculate price position
        range_size = recent_high - recent_low
        if range_size > 0:
            price_position = (current_price - recent_low) / range_size
        else:
            price_position = 0.5
            
        return {
            'price_position': price_position,
            'recent_high': recent_high,
            'recent_low': recent_low,
            'range_size': range_size
        }