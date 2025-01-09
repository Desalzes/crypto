import pandas as pd
from typing import Dict, Optional
from core.indicators import Indicators
import logging

class CryptoStrategy:
    def __init__(self, db):
        self.db = db
        self.logger = logging.getLogger(__name__)
        
    def calculate_position_size(self, portfolio_value: float, confidence: float, price: float) -> float:
        base_size = portfolio_value * 0.02  # 2% risk per trade
        return min(base_size, portfolio_value * 0.1)  # Max 10% of portfolio

    async def analyze_all_timeframes(self, pair: str, ticker: Dict, ohlcv: Dict) -> Optional[Dict]:
        try:
            if not ticker or not ohlcv:
                return None

            timeframe_scores = {}
            for timeframe, df in ohlcv.items():
                if df.empty:
                    continue
                    
                indicators = Indicators.calculate_all(df, timeframe)
                score = self._analyze_timeframe(indicators)
                timeframe_scores[timeframe] = score

            if not timeframe_scores:
                return None

            combined_score = self._calculate_combined_score(timeframe_scores)
            action, confidence = self._determine_action(combined_score)
            
            return {
                'action': action,
                'confidence': confidence,
                'summary': f"Score: {combined_score:.2f}",
                'signals': timeframe_scores
            }

        except Exception as e:
            self.logger.error(f"Error analyzing {pair}: {e}")
            return None

    def _analyze_timeframe(self, indicators: Dict) -> float:
        try:
            score = 0.0
            
            # RSI Rules
            rsi = indicators.get('rsi', 50)
            if rsi < 30:  # Oversold
                score += 0.4
            elif rsi > 70:  # Overbought
                score -= 0.4
                
            # MACD Rules
            macd = indicators.get('macd', 0)
            macd_signal = indicators.get('macd_signal', 0)
            if macd > macd_signal:
                score += 0.3
            else:
                score -= 0.3
                
            # Bollinger Bands Rules
            bb_lower = indicators.get('bb_lower', 0)
            bb_upper = indicators.get('bb_upper', 0)
            bb_mid = indicators.get('bb_mid', 0)
            current_price = indicators.get('close', bb_mid)
            
            if current_price < bb_lower:  # Below lower band
                score += 0.3
            elif current_price > bb_upper:  # Above upper band
                score -= 0.3
                
            # EMA Rules
            ema_short = indicators.get('ema_short', 0)
            ema_long = indicators.get('ema_long', 0)
            if ema_short > ema_long:  # Bullish trend
                score += 0.2
            else:  # Bearish trend
                score -= 0.2
                
            return score
            
        except Exception as e:
            self.logger.error(f"Error in timeframe analysis: {e}")
            return 0.0

    def _calculate_combined_score(self, timeframe_scores: Dict[str, float]) -> float:
        weights = {
            '1m': 0.1,
            '5m': 0.2,
            '15m': 0.3,
            '1h': 0.4
        }
        
        weighted_sum = 0
        weight_sum = 0
        
        for timeframe, score in timeframe_scores.items():
            weight = weights.get(timeframe, 0.1)
            weighted_sum += score * weight
            weight_sum += weight
            
        return weighted_sum / weight_sum if weight_sum > 0 else 0

    def _determine_action(self, score: float) -> tuple:
        if score > 0.3:  # Stronger buy signal
            confidence = min((score - 0.3) * 2, 1.0)
            return 'BUY', confidence
        elif score < -0.3:  # Stronger sell signal
            confidence = min((abs(score) - 0.3) * 2, 1.0)
            return 'SELL', confidence
        else:
            return 'HOLD', 0.0