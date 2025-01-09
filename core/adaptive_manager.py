import pandas as pd
import numpy as np
from datetime import datetime, time
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)

class AdaptiveManager:
    def __init__(self):
        self.vol_lookback = 20  # Days to look back for volatility comparison
        self.trend_lookback = 200  # Days for trend determination
        self.volume_ma_period = 20  # Days for volume moving average
        self.hour_performance = {}  # Track performance by hour
        
    def detect_market_regime(self, df: pd.DataFrame) -> Dict:
        """
        Detect current market regime using multiple indicators
        Returns: Dictionary with regime information
        """
        # Calculate long-term trend using 200 EMA
        ema200 = df['close'].ewm(span=200, adjust=False).mean()
        
        # Calculate ADX for trend strength
        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - df['close'].shift())
        tr3 = abs(df['low'] - df['close'].shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        dx = pd.Series(0.0, index=df.index)
        atr = tr.rolling(14).mean()
        
        plus_dm = df['high'].diff()
        minus_dm = df['low'].diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
        minus_di = 100 * (minus_dm.abs().rolling(14).mean() / atr)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(14).mean()
        
        current_price = df['close'].iloc[-1]
        current_ema = ema200.iloc[-1]
        current_adx = adx.iloc[-1]
        
        # Determine regime
        if current_price > current_ema and current_adx > 25:
            regime = "strong_uptrend"
        elif current_price < current_ema and current_adx > 25:
            regime = "strong_downtrend"
        elif current_adx <= 25:
            regime = "choppy"
        else:
            regime = "neutral"
            
        return {
            "regime": regime,
            "trend_strength": current_adx,
            "price_to_ema": current_price / current_ema - 1
        }
        
    def analyze_volatility(self, df: pd.DataFrame) -> Dict:
        """
        Analyze current volatility conditions
        Returns: Dictionary with volatility metrics
        """
        # Calculate ATR
        atr = df['high'] - df['low']
        atr_ma = atr.rolling(self.vol_lookback).mean()
        
        # Get current ATR percentile
        current_atr = atr.iloc[-1]
        atr_percentile = len(atr[atr <= current_atr]) / len(atr)
        
        # Calculate historical volatility using log returns
        returns = np.log(df['close'] / df['close'].shift(1))
        hist_vol = returns.std() * np.sqrt(252)  # Annualized
        
        return {
            "atr": current_atr,
            "atr_percentile": atr_percentile,
            "historical_volatility": hist_vol,
            "is_high_volatility": atr_percentile > 0.7
        }
        
    def analyze_volume(self, df: pd.DataFrame) -> Dict:
        """
        Analyze current volume conditions
        Returns: Dictionary with volume metrics
        """
        volume_ma = df['volume'].rolling(self.volume_ma_period).mean()
        current_volume = df['volume'].iloc[-1]
        relative_volume = current_volume / volume_ma.iloc[-1]
        
        return {
            "relative_volume": relative_volume,
            "is_high_volume": relative_volume > 1.5,
            "is_low_volume": relative_volume < 0.5
        }
        
    def adjust_thresholds(self, base_thresholds: Dict, market_conditions: Dict) -> Dict:
        """
        Dynamically adjust trading thresholds based on market conditions
        """
        regime = market_conditions['regime']
        vol_data = market_conditions['volatility']
        volume_data = market_conditions['volume']
        
        adjusted = base_thresholds.copy()
        
        # Adjust based on regime
        if regime == "choppy":
            adjusted['stop_loss'] *= 1.5  # Wider stops in choppy markets
            adjusted['position_size'] *= 0.7  # Reduce position size
            adjusted['min_confidence'] *= 1.2  # Require higher confidence
            
        elif regime == "strong_uptrend":
            adjusted['trailing_stop'] = True  # Enable trailing stops
            adjusted['take_profit'] *= 1.5  # Let winners run more
            
        elif regime == "strong_downtrend":
            adjusted['position_size'] *= 0.5  # Reduce size in downtrends
            adjusted['stop_loss'] *= 1.2  # Wider stops
            
        # Adjust for volatility
        if vol_data['is_high_volatility']:
            adjusted['position_size'] *= 0.8
            adjusted['stop_loss'] *= 1.3
            adjusted['min_confidence'] *= 1.1
            
        # Adjust for volume
        if volume_data['is_low_volume']:
            adjusted['position_size'] *= 0.7
            adjusted['min_confidence'] *= 1.2
            
        return adjusted
        
    def analyze_hour_performance(self, hour: int, success: bool):
        """Track performance by hour"""
        if hour not in self.hour_performance:
            self.hour_performance[hour] = {'wins': 0, 'total': 0}
        
        self.hour_performance[hour]['total'] += 1
        if success:
            self.hour_performance[hour]['wins'] += 1
            
    def get_time_based_adjustments(self, current_time: datetime) -> Dict:
        """Get trading adjustments based on time of day"""
        hour = current_time.hour
        
        # Get win rate for current hour if we have data
        if hour in self.hour_performance and self.hour_performance[hour]['total'] > 0:
            win_rate = self.hour_performance[hour]['wins'] / self.hour_performance[hour]['total']
        else:
            win_rate = 0.5  # Default if no data
            
        # Define adjustments based on historical performance
        adjustments = {
            'should_trade': True,
            'position_size_multiplier': 1.0,
            'confidence_multiplier': 1.0
        }
        
        # Reduce activity during historically poor performing hours
        if win_rate < 0.4 and self.hour_performance[hour]['total'] > 10:
            adjustments['should_trade'] = False
            
        # Increase size during historically good hours
        elif win_rate > 0.6 and self.hour_performance[hour]['total'] > 10:
            adjustments['position_size_multiplier'] = 1.2
            adjustments['confidence_multiplier'] = 0.9
            
        return adjustments
        
    def analyze_market_conditions(self, df: pd.DataFrame) -> Dict:
        """
        Comprehensive market analysis combining all factors
        """
        regime_data = self.detect_market_regime(df)
        vol_data = self.analyze_volatility(df)
        volume_data = self.analyze_volume(df)
        time_data = self.get_time_based_adjustments(datetime.now())
        
        return {
            "regime": regime_data,
            "volatility": vol_data,
            "volume": volume_data,
            "time": time_data
        }