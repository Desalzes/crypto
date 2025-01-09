import pandas as pd
import numpy as np
from typing import Dict, List

class PatternRecognizer:
    def __init__(self):
        self.is_three_line_strike = False
        self.candlestick_patterns = {
            'doji': self._is_doji,
            'hammer': self._is_hammer,
            'engulfing': self._is_engulfing,
            'three_line_strike': self._is_three_line_strike
        }

        self.technical_patterns = {
            'double_top': self._is_double_top,
            'double_bottom': self._is_double_bottom,
            'head_shoulders': self._is_head_shoulders,
            'triangle': self._is_triangle,
            'channel': self._is_channel
        }

    def analyze_patterns(self, df: pd.DataFrame) -> Dict:
        try:
            results = {
                'candlestick_patterns': self._analyze_candlestick_patterns(df),
                'technical_patterns': self._analyze_technical_patterns(df),
                'support_resistance': self._find_support_resistance(df),
                'trend_lines': self._find_trend_lines(df)
            }
            return results
        except Exception as e:
            return self._default_analysis()

    def _calculate_pattern_strength(self, pattern: Dict) -> float:
        if not pattern:
            return 0
            
        volume_factor = pattern.get('volume_confirmation', 1)
        trend_alignment = pattern.get('trend_alignment', 1)
        pattern_quality = pattern.get('quality', 1)
        
        return min(volume_factor * trend_alignment * pattern_quality, 1.0)

    def _default_analysis(self) -> Dict:
        return {
            'candlestick_patterns': [],
            'technical_patterns': [],
            'support_resistance': {'support': [], 'resistance': []},
            'trend_lines': {'upper': None, 'lower': None}
        }

    def _analyze_candlestick_patterns(self, df: pd.DataFrame) -> List[Dict]:
        patterns = []
        for i in range(min(10, len(df))):  # Look at last 10 candles
            window = df.iloc[max(0, i-3):i+1]  # 3 candle window
            for pattern_name, pattern_func in self.candlestick_patterns.items():
                if pattern_func(window):
                    strength = self._calculate_pattern_strength({
                        'quality': pattern_func(window, return_strength=True),
                        'volume_confirmation': self._check_volume_confirmation(df, i),
                        'trend_alignment': self._check_trend_alignment(df, i)
                    })
                    
                    patterns.append({
                        'type': pattern_name,
                        'location': i,
                        'strength': strength,
                        'price_level': df.iloc[i]['close']
                    })
                    
        return patterns

    def _is_three_line_strike(self, window: pd.DataFrame, return_strength: bool = False) -> bool:
        if len(window) < 4:
            return False if not return_strength else 0.0
            
        last_3_candles = window.iloc[-4:-1]
        strike_candle = window.iloc[-1]
        
        # Check for 3 consecutive bearish candles
        is_bearish = [c['close'] < c['open'] for _, c in last_3_candles.iterrows()]
        if not all(is_bearish):
            return False if not return_strength else 0.0
            
        # Check if each close is lower than previous
        closes = last_3_candles['close'].values
        if not all(closes[i] > closes[i+1] for i in range(len(closes)-1)):
            return False if not return_strength else 0.0
            
        # Check bullish strike candle
        if not (strike_candle['close'] > strike_candle['open'] and
                strike_candle['close'] > last_3_candles.iloc[0]['open']):
            return False if not return_strength else 0.0
            
        # Calculate pattern strength
        bearish_size = sum(abs(c['open'] - c['close']) for _, c in last_3_candles.iterrows())
        strike_size = abs(strike_candle['close'] - strike_candle['open'])
        strength = min(strike_size / bearish_size if bearish_size > 0 else 0, 1.0)
        
        return strength if return_strength else True

    def _is_doji(self, window: pd.DataFrame, return_strength: bool = False) -> bool:
        if len(window) < 1:
            return False if not return_strength else 0.0
            
        candle = window.iloc[-1]
        body_size = abs(candle['open'] - candle['close'])
        total_size = candle['high'] - candle['low']
        
        if total_size == 0:
            return False if not return_strength else 0.0
            
        body_ratio = body_size / total_size
        strength = 1 - body_ratio
        
        if return_strength:
            return strength
            
        return body_ratio < 0.1

    def _is_hammer(self, window: pd.DataFrame, return_strength: bool = False) -> bool:
        if len(window) < 1:
            return False if not return_strength else 0.0
            
        candle = window.iloc[-1]
        body_size = abs(candle['open'] - candle['close'])
        upper_wick = candle['high'] - max(candle['open'], candle['close'])
        lower_wick = min(candle['open'], candle['close']) - candle['low']
        
        if body_size == 0:
            return False if not return_strength else 0.0
            
        lower_ratio = lower_wick / body_size
        upper_ratio = upper_wick / body_size
        
        strength = lower_ratio * (1 - upper_ratio)
        
        if return_strength:
            return min(strength, 1.0)
            
        return lower_ratio > 2 and upper_ratio < 0.5

    def _is_engulfing(self, window: pd.DataFrame, return_strength: bool = False) -> bool:
        if len(window) < 2:
            return False if not return_strength else 0.0
            
        current = window.iloc[-1]
        previous = window.iloc[-2]
        
        current_body_size = abs(current['close'] - current['open'])
        previous_body_size = abs(previous['close'] - previous['open'])
        
        if previous_body_size == 0:
            return False if not return_strength else 0.0
            
        size_ratio = current_body_size / previous_body_size
        
        current_bullish = current['close'] > current['open']
        previous_bullish = previous['close'] > previous['open']
        
        is_engulfing = (
            size_ratio > 1 and
            current_bullish != previous_bullish and
            ((current_bullish and current['open'] < previous['close']) or
             (not current_bullish and current['open'] > previous['close']))
        )
        
        if return_strength:
            return min(size_ratio - 1, 1.0) if is_engulfing else 0.0
            
        return is_engulfing

    def _is_double_top(self, window: pd.DataFrame) -> bool:
        # Implementation for double top pattern
        return False

    def _is_double_bottom(self, window: pd.DataFrame) -> bool:
        # Implementation for double bottom pattern
        return False

    def _is_head_shoulders(self, window: pd.DataFrame) -> bool:
        # Implementation for head and shoulders pattern
        return False

    def _is_triangle(self, window: pd.DataFrame) -> bool:
        # Implementation for triangle pattern
        return False

    def _is_channel(self, window: pd.DataFrame) -> bool:
        # Implementation for channel pattern
        return False

    def _check_volume_confirmation(self, df: pd.DataFrame, idx: int) -> float:
        if idx < 1 or idx >= len(df):
            return 1.0
            
        current_volume = df.iloc[idx]['volume']
        avg_volume = df['volume'].rolling(20).mean().iloc[idx]
        
        if avg_volume == 0:
            return 1.0
            
        volume_ratio = current_volume / avg_volume
        return min(volume_ratio, 2.0) / 2.0

    def _check_trend_alignment(self, df: pd.DataFrame, idx: int) -> float:
        if idx < 20 or idx >= len(df):
            return 1.0
            
        current_price = df.iloc[idx]['close']
        sma20 = df['close'].rolling(20).mean().iloc[idx]
        
        if abs(current_price - sma20) < 0.001:
            return 1.0
            
        price_trend = (current_price - sma20) / sma20
        return min(abs(price_trend) * 10, 1.0)

    def _find_support_resistance(self, df: pd.DataFrame) -> Dict:
        pivots = self._find_pivot_points(df)
        levels = {
            'support': self._cluster_levels(pivots['lows']),
            'resistance': self._cluster_levels(pivots['highs'])
        }
        return levels

    def _find_pivot_points(self, df: pd.DataFrame, window: int = 5) -> Dict:
        highs = []
        lows = []
        
        for i in range(window, len(df) - window):
            if df.iloc[i]['high'] == max(df.iloc[i-window:i+window+1]['high']):
                highs.append(df.iloc[i]['high'])
            if df.iloc[i]['low'] == min(df.iloc[i-window:i+window+1]['low']):
                lows.append(df.iloc[i]['low'])
                
        return {'highs': highs, 'lows': lows}

    def _cluster_levels(self, prices: List[float], threshold: float = 0.02) -> List[float]:
        if not prices:
            return []
            
        clusters = []
        current_cluster = [prices[0]]
        
        for price in sorted(prices[1:]):
            if abs(price - sum(current_cluster)/len(current_cluster)) / price <= threshold:
                current_cluster.append(price)
            else:
                clusters.append(sum(current_cluster)/len(current_cluster))
                current_cluster = [price]
                
        if current_cluster:
            clusters.append(sum(current_cluster)/len(current_cluster))
            
        return clusters

    def _find_trend_lines(self, df: pd.DataFrame) -> Dict:
        highs = df['high'].values
        lows = df['low'].values
        
        high_points = self._find_swings(highs, 'high')
        low_points = self._find_swings(lows, 'low')
        
        upper_line = self._fit_trend_line(high_points) if high_points else None
        lower_line = self._fit_trend_line(low_points) if low_points else None
        
        return {
            'upper': upper_line,
            'lower': lower_line,
            'channel_quality': self._calculate_channel_quality(df, upper_line, lower_line)
        }

    def _find_swings(self, data: np.array, swing_type: str, lookback: int = 5) -> List[tuple]:
        points = []
        for i in range(lookback, len(data) - lookback):
            if swing_type == 'high':
                if data[i] == max(data[i-lookback:i+lookback+1]):
                    points.append((i, data[i]))
            else:
                if data[i] == min(data[i-lookback:i+lookback+1]):
                    points.append((i, data[i]))
        return points

    def _fit_trend_line(self, points: List[tuple]) -> Dict:
        if len(points) < 2:
            return None
            
        x = np.array([p[0] for p in points])
        y = np.array([p[1] for p in points])
        
        coeffs = np.polyfit(x, y, 1)
        return {
            'slope': coeffs[0],
            'intercept': coeffs[1],
            'points': points
        }

    def _calculate_channel_quality(self, df: pd.DataFrame, upper_line: Dict, lower_line: Dict) -> float:
        if not upper_line or not lower_line:
            return 0.0
            
        slope_diff = abs(upper_line['slope'] - lower_line['slope'])
        if slope_diff > 0.1:
            return 0.0
            
        touches = self._count_line_touches(df, upper_line) + \
                 self._count_line_touches(df, lower_line)
                     
        quality = min(touches / 10, 1.0) * (1 - slope_diff * 5)
        return max(quality, 0.0)

    def _count_line_touches(self, df: pd.DataFrame, line: Dict) -> int:
        touches = 0
        x = np.arange(len(df))
        y = line['slope'] * x + line['intercept']
        
        for i in range(len(df)):
            price = df.iloc[i]['close']
            line_price = y[i]
            if abs(price - line_price) / price <= 0.001:
                touches += 1
                
        return touches