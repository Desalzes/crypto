import pandas as pd
from typing import Dict, Optional
from core.indicators import Indicators

class CryptoStrategy:
    def __init__(self):
        self.weights = {
            'RSI': 0.3,
            'MACD': 0.25,
            'BB': 0.25,
            'EMA': 0.2
        }
        
    def calculate_position_size(self, portfolio_value: float, confidence: float, price: float) -> float:
        base_size = portfolio_value * 0.02
        adjusted_size = base_size * confidence
        return min(adjusted_size, portfolio_value * 0.1)

    def _analyze_timeframe(self, indicators: Dict) -> float:
        try:
            score = 0.0
            
            rsi = indicators.get('rsi', 50)
            if rsi < 45:
                score += 0.4
            elif rsi > 55:
                score -= 0.4
                
            macd = indicators.get('macd', 0)
            macd_signal = indicators.get('macd_signal', 0)
            if macd > macd_signal * 0.7:
                score += 0.3
            else:
                score -= 0.3
                
            bb_lower = indicators.get('bb_lower', 0)
            bb_upper = indicators.get('bb_upper', 0)
            bb_mid = indicators.get('bb_mid', 0)
            current_price = indicators.get('close', bb_mid)
            
            if current_price < bb_mid * 0.99:
                score += 0.3
            elif current_price > bb_mid * 1.01:
                score -= 0.3
                
            ema_short = indicators.get('ema_short', 0)
            ema_long = indicators.get('ema_long', 0)
            if ema_short > ema_long * 0.98:
                score += 0.2
            else:
                score -= 0.2
                
            return score
            
        except Exception as e:
            print(f"Error in timeframe analysis: {e}")
            return 0.0

    def _calculate_combined_score(self, timeframe_scores: Dict[str, float]) -> float:
        weights = {
            '1m': 0.1,
            '5m': 0.2,
            '15m': 0.3,
            '1h': 0.4,
            '4h': 0.5,
            '1d': 0.6
        }
        
        weighted_sum = 0
        weight_sum = 0
        
        for timeframe, score in timeframe_scores.items():
            weight = weights.get(timeframe, 0.1)
            weighted_sum += score * weight
            weight_sum += weight
            
        return weighted_sum / weight_sum if weight_sum > 0 else 0

    def _determine_action(self, score: float) -> tuple:
        if score > 0.27:
            confidence = min((score - 0.27) * 2, 1.0)
            return 'BUY', confidence
        elif score < -0.27:
            confidence = min((abs(score) - 0.27) * 2, 1.0)
            return 'SELL', confidence
        else:
            return 'HOLD', 0.0