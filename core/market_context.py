import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class MarketState:
    regime: str
    volatility: str
    liquidity: str
    trend_strength: float
    key_levels: Dict[str, float]
    recent_patterns: List[Dict]
    risk_level: str
    trading_suggestions: Dict

class MarketContextAnalyzer:
    def __init__(self):
        self.timeframes = ['1m', '5m', '15m', '1h']
        self.weights = {
            '1m': 0.1,
            '5m': 0.2,
            '15m': 0.3,
            '1h': 0.4
        }

    def analyze_market_context(self, data: Dict[str, pd.DataFrame]) -> Dict:
        tf_analyses = {}
        for tf, df in data.items():
            if tf in self.timeframes and not df.empty:
                tf_analyses[tf] = self._analyze_timeframe(df)

        return self._combine_timeframe_analyses(tf_analyses)

    def _analyze_timeframe(self, df: pd.DataFrame) -> Dict:
        volatility = self._analyze_volatility(df)
        trend = self._analyze_trend(df)
        support_resistance = self._analyze_support_resistance(df)

        return {
            'volatility': volatility,
            'trend': trend,
            'support_resistance': support_resistance
        }

    def _analyze_volatility(self, df: pd.DataFrame) -> Dict:
        returns = df['close'].pct_change()
        volatility = returns.std()
        
        if volatility > 0.02:
            level = 'HIGH'
        elif volatility > 0.01:
            level = 'MEDIUM'
        else:
            level = 'LOW'

        return {
            'level': level,
            'value': float(volatility),
            'is_expanding': self._is_volatility_expanding(returns)
        }

    def _analyze_trend(self, df: pd.DataFrame) -> Dict:
        ema_short = df['close'].ewm(span=20).mean()
        ema_long = df['close'].ewm(span=50).mean()
        
        trend_strength = abs((ema_short.iloc[-1] - ema_long.iloc[-1]) / ema_long.iloc[-1])
        
        if trend_strength > 0.02:
            if ema_short.iloc[-1] > ema_long.iloc[-1]:
                regime = 'STRONG_UPTREND'
            else:
                regime = 'STRONG_DOWNTREND'
        elif trend_strength > 0.01:
            if ema_short.iloc[-1] > ema_long.iloc[-1]:
                regime = 'WEAK_UPTREND'
            else:
                regime = 'WEAK_DOWNTREND'
        else:
            regime = 'RANGING'

        return {
            'regime': regime,
            'strength': float(trend_strength),
            'direction': 'UP' if ema_short.iloc[-1] > ema_long.iloc[-1] else 'DOWN'
        }

    def _analyze_support_resistance(self, df: pd.DataFrame) -> Dict:
        window = 20
        high_levels = df['high'].rolling(window=window).max()
        low_levels = df['low'].rolling(window=window).min()
        
        current_price = df['close'].iloc[-1]
        nearest_resistance = high_levels.iloc[-1]
        nearest_support = low_levels.iloc[-1]

        return {
            'nearest_support': float(nearest_support),
            'nearest_resistance': float(nearest_resistance),
            'price_location': (current_price - nearest_support) / (nearest_resistance - nearest_support)
        }

    def _is_volatility_expanding(self, returns: pd.Series) -> bool:
        recent_vol = returns.tail(10).std()
        older_vol = returns.iloc[-20:-10].std()
        return recent_vol > older_vol

    def _combine_timeframe_analyses(self, tf_analyses: Dict) -> Dict:
        if not tf_analyses:
            return self._default_analysis()

        # Combine volatility
        weighted_vol = 0
        total_weight = 0
        vol_expanding = False

        # Combine trend signals
        trend_strength = 0
        regime_votes = {}

        for tf, analysis in tf_analyses.items():
            weight = self.weights.get(tf, 0.1)
            
            # Volatility
            vol_level = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2}[analysis['volatility']['level']]
            weighted_vol += vol_level * weight
            total_weight += weight
            if analysis['volatility']['is_expanding']:
                vol_expanding = True

            # Trend
            trend_strength += analysis['trend']['strength'] * weight
            regime = analysis['trend']['regime']
            regime_votes[regime] = regime_votes.get(regime, 0) + weight

        # Calculate final values
        avg_vol = weighted_vol / total_weight if total_weight > 0 else 1
        final_vol = 'HIGH' if avg_vol > 1.5 else 'MEDIUM' if avg_vol > 0.5 else 'LOW'

        # Determine overall regime
        overall_regime = max(regime_votes.items(), key=lambda x: x[1])[0]

        return {
            'regime': overall_regime,
            'volatility': final_vol,
            'trend_strength': float(trend_strength),
            'is_volatility_expanding': vol_expanding,
            'risk_level': 'HIGH' if final_vol == 'HIGH' else 'MEDIUM' if final_vol == 'MEDIUM' else 'LOW'
        }

    def _default_analysis(self) -> Dict:
        return {
            'regime': 'UNKNOWN',
            'volatility': 'HIGH',
            'trend_strength': 0.0,
            'is_volatility_expanding': False,
            'risk_level': 'HIGH'
        }