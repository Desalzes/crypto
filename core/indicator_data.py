import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class IndicatorMetrics:
    value: float
    signal: str
    reliability: float
    trend: str
    divergence: Optional[bool] = None
    warning_signals: List[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'value': self.value,
            'signal': self.signal,
            'reliability': self.reliability,
            'trend': self.trend,
            'divergence': self.divergence,
            'warning_signals': self.warning_signals or []
        }

class StructuredIndicatorData:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.indicators = {}
        self.calculate_all_indicators()

    def calculate_all_indicators(self):
        """Calculate and structure all indicator data"""
        self.indicators['rsi'] = self._analyze_rsi()
        self.indicators['macd'] = self._analyze_macd()
        self.indicators['bollinger'] = self._analyze_bollinger()
        self.indicators['ema'] = self._analyze_ema_indicator()
        self.indicators['volume'] = self._analyze_volume()
        self.indicators['momentum'] = self._analyze_momentum()

    def _analyze_rsi(self, period: int = 14) -> IndicatorMetrics:
        """Analyze RSI with structured output"""
        delta = self.df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = pd.Series(100 - (100 / (1 + rs)), index=self.df.index)
        
        current_rsi = rsi.iloc[-1]
        
        # Determine signal
        if current_rsi > 70:
            signal = 'SELL'
        elif current_rsi < 30:
            signal = 'BUY'
        else:
            signal = 'NEUTRAL'
            
        # Check for divergence
        price_trend = self.df['close'].iloc[-5:].is_monotonic_increasing
        rsi_trend = rsi.iloc[-5:].is_monotonic_increasing
        divergence = price_trend != rsi_trend
        
        reliability = self._calculate_indicator_reliability(rsi, self.df['close'])
        
        rsi_sma = rsi.rolling(5).mean()
        trend = 'UPWARD' if rsi_sma.iloc[-1] > rsi_sma.iloc[-2] else 'DOWNWARD'
        
        warnings = []
        if divergence:
            warnings.append('RSI showing divergence with price')
        if 69 < current_rsi < 71 or 29 < current_rsi < 31:
            warnings.append('RSI near reversal level')
            
        return IndicatorMetrics(
            value=current_rsi,
            signal=signal,
            reliability=reliability,
            trend=trend,
            divergence=divergence,
            warning_signals=warnings
        )

    def _analyze_macd(self) -> IndicatorMetrics:
        """Analyze MACD with structured output"""
        exp1 = self.df['close'].ewm(span=12, adjust=False).mean()
        exp2 = self.df['close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        
        current_macd = macd.iloc[-1]
        current_signal = signal.iloc[-1]
        
        # Determine signal based on crossovers
        if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]:
            trade_signal = 'BUY'
        elif macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2]:
            trade_signal = 'SELL'
        else:
            trade_signal = 'NEUTRAL'
            
        # Check for divergence
        price_trend = self.df['close'].iloc[-5:].is_monotonic_increasing
        macd_trend = macd.iloc[-5:].is_monotonic_increasing
        divergence = price_trend != macd_trend
        
        reliability = self._calculate_indicator_reliability(macd, self.df['close'])
        
        trend = 'UPWARD' if current_macd > current_signal else 'DOWNWARD'
        
        warnings = []
        if divergence:
            warnings.append('MACD showing divergence with price')
        if abs(current_macd - current_signal) < 0.1 * abs(current_macd):
            warnings.append('MACD close to signal line')
            
        return IndicatorMetrics(
            value=current_macd,
            signal=trade_signal,
            reliability=reliability,
            trend=trend,
            divergence=divergence,
            warning_signals=warnings
        )

    def _analyze_bollinger(self, period: int = 20, std_dev: int = 2) -> IndicatorMetrics:
        """Analyze Bollinger Bands with structured output"""
        try:
            sma = self.df['close'].rolling(window=period).mean()
            rolling_std = self.df['close'].rolling(window=period).std()
            
            upper_band = sma + (rolling_std * std_dev)
            lower_band = sma - (rolling_std * std_dev)
            
            current_price = self.df['close'].iloc[-1]
            current_upper = upper_band.iloc[-1]
            current_lower = lower_band.iloc[-1]
            current_sma = sma.iloc[-1]
            
            # Calculate bandwidth
            bandwidth = (current_upper - current_lower) / current_sma
            
            # Determine signal
            if current_price >= current_upper:
                signal = 'SELL'
            elif current_price <= current_lower:
                signal = 'BUY'
            else:
                signal = 'NEUTRAL'
                
            # Calculate reliability based on historical band touches
            reliability = self._calculate_bb_reliability(upper_band, lower_band, self.df['close'])
            
            # Determine trend
            trend = 'UPWARD' if sma.iloc[-1] > sma.iloc[-5] else 'DOWNWARD'
            
            warnings = []
            if bandwidth < 0.1:  # Narrow bands suggest potential breakout
                warnings.append('Bollinger Bands squeezing - potential breakout')
            if abs(current_price - current_upper) / current_price < 0.002:
                warnings.append('Price testing upper band')
            if abs(current_price - current_lower) / current_price < 0.002:
                warnings.append('Price testing lower band')
                
            return IndicatorMetrics(
                value=current_price,
                signal=signal,
                reliability=reliability,
                trend=trend,
                warning_signals=warnings
            )
        except Exception as e:
            print(f"Error in Bollinger analysis: {e}")
            return self._default_metrics()

    def _analyze_ema_indicator(self) -> IndicatorMetrics:
        """Analyze EMAs with structured output"""
        try:
            ema_short = self.df['close'].ewm(span=12, adjust=False).mean()
            ema_long = self.df['close'].ewm(span=26, adjust=False).mean()
            
            current_short = ema_short.iloc[-1]
            current_long = ema_long.iloc[-1]
            current_price = self.df['close'].iloc[-1]
            
            # Determine signal
            if current_price > current_short > current_long:
                signal = 'BUY'
            elif current_price < current_short < current_long:
                signal = 'SELL'
            else:
                signal = 'NEUTRAL'
                
            # Calculate trend strength
            trend_strength = abs(current_short - current_long) / current_long
            reliability = min(trend_strength * 2, 1.0)  # Scale trend strength to 0-1
            
            trend = 'UPWARD' if current_short > current_long else 'DOWNWARD'
            
            warnings = []
            if abs(current_short - current_long) / current_long < 0.001:
                warnings.append('EMAs converging - potential trend change')
            if abs(current_price - current_short) / current_price > 0.02:
                warnings.append('Price diverging significantly from EMA')
                
            return IndicatorMetrics(
                value=current_short,  # Use short EMA as main value
                signal=signal,
                reliability=reliability,
                trend=trend,
                warning_signals=warnings
            )
        except Exception as e:
            print(f"Error in EMA analysis: {e}")
            return self._default_metrics()

    def _analyze_volume(self) -> IndicatorMetrics:
        """Analyze volume patterns and trends"""
        try:
            current_volume = self.df['volume'].iloc[-1]
            avg_volume = self.df['volume'].rolling(20).mean().iloc[-1]
            
            # Calculate volume trend
            volume_sma = self.df['volume'].rolling(5).mean()
            trend = 'UPWARD' if volume_sma.iloc[-1] > volume_sma.iloc[-5] else 'DOWNWARD'
            
            # Volume-price relationship
            price_up = self.df['close'].iloc[-1] > self.df['close'].iloc[-2]
            volume_signal = 'BUY' if price_up and current_volume > avg_volume else \
                          'SELL' if not price_up and current_volume > avg_volume else \
                          'NEUTRAL'
                          
            # Calculate reliability based on volume-price correlation
            reliability = self._calculate_volume_reliability()
            
            warnings = []
            if current_volume < 0.5 * avg_volume:
                warnings.append('Low volume - potential lack of conviction')
            if current_volume > 2 * avg_volume:
                warnings.append('Unusually high volume - monitor for reversal')
                
            return IndicatorMetrics(
                value=current_volume,
                signal=volume_signal,
                reliability=reliability,
                trend=trend,
                warning_signals=warnings
            )
        except Exception as e:
            print(f"Error in volume analysis: {e}")
            return self._default_metrics()

    def _analyze_momentum(self) -> IndicatorMetrics:
        """Analyze price momentum indicators"""
        try:
            # Calculate ROC
            roc = ((self.df['close'] - self.df['close'].shift(10)) / 
                  self.df['close'].shift(10) * 100)
            
            current_roc = roc.iloc[-1]
            
            # Determine momentum signal
            if current_roc > 2:
                signal = 'BUY'
            elif current_roc < -2:
                signal = 'SELL'
            else:
                signal = 'NEUTRAL'
                
            # Calculate momentum trend
            roc_sma = roc.rolling(5).mean()
            trend = 'UPWARD' if roc_sma.iloc[-1] > roc_sma.iloc[-5] else 'DOWNWARD'
            
            # Calculate reliability
            reliability = self._calculate_momentum_reliability(roc)
            
            warnings = []
            if abs(current_roc) > 5:
                warnings.append('Extreme momentum - potential reversal')
            if roc.iloc[-1] * roc.iloc[-2] < 0:
                warnings.append('Momentum direction change')
                
            return IndicatorMetrics(
                value=current_roc,
                signal=signal,
                reliability=reliability,
                trend=trend,
                warning_signals=warnings
            )
        except Exception as e:
            print(f"Error in momentum analysis: {e}")
            return self._default_metrics()

    def _calculate_indicator_reliability(self, indicator: pd.Series, price: pd.Series) -> float:
        """Calculate historical reliability of an indicator"""
        try:
            # Calculate correlation between indicator changes and subsequent price changes
            indicator_changes = indicator.diff()
            future_returns = price.shift(-1).diff()
            correlation = indicator_changes.corr(future_returns)
            
            # Scale correlation to 0-1 range
            reliability = (correlation + 1) / 2
            return min(max(reliability, 0), 1)
        except:
            return 0.5

    def _calculate_bb_reliability(self, upper: pd.Series, lower: pd.Series, 
                                price: pd.Series) -> float:
        """Calculate Bollinger Bands reliability"""
        try:
            touches = 0
            successes = 0
            
            for i in range(1, len(price)):
                if price.iloc[i-1] <= lower.iloc[i-1] and price.iloc[i] > lower.iloc[i]:
                    touches += 1
                    if price.iloc[i:i+5].mean() > price.iloc[i]:
                        successes += 1
                elif price.iloc[i-1] >= upper.iloc[i-1] and price.iloc[i] < upper.iloc[i]:
                    touches += 1
                    if price.iloc[i:i+5].mean() < price.iloc[i]:
                        successes += 1
                        
            return successes / touches if touches > 0 else 0.5
        except:
            return 0.5

    def _calculate_volume_reliability(self) -> float:
        """Calculate volume indicator reliability"""
        try:
            # Correlation between volume and absolute price changes
            volume = self.df['volume']
            price_changes = self.df['close'].pct_change().abs()
            correlation = volume.corr(price_changes)
            
            # Scale to 0-1
            return min(max((correlation + 1) / 2, 0), 1)
        except:
            return 0.5

    def _calculate_momentum_reliability(self, momentum: pd.Series) -> float:
        """Calculate momentum indicator reliability"""
        try:
            # Compare momentum direction with future returns
            momentum_direction = momentum > 0
            future_returns = self.df['close'].shift(-5).diff(5) > 0
            
            # Calculate accuracy of momentum predictions
            correct_predictions = (momentum_direction == future_returns).mean()
            return correct_predictions
        except:
            return 0.5

    def _default_metrics(self) -> IndicatorMetrics:
        """Return default metrics when analysis fails"""
        return IndicatorMetrics(
            value=0.0,
            signal='NEUTRAL',
            reliability=0.0,
            trend='NEUTRAL',
            divergence=False,
            warning_signals=['Analysis failed']
        )

    def get_combined_analysis(self) -> Dict:
        """Get comprehensive analysis of all indicators"""
        return {name: ind.to_dict() for name, ind in self.indicators.items()}