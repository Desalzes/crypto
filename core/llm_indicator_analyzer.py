import logging
from typing import Dict, List
import numpy as np
import json
import time

logger = logging.getLogger(__name__)

class LLMIndicatorAnalyzer:
    def __init__(self):
        self.indicator_weights = {
            'RSI': 0.25,
            'MACD': 0.25,
            'BB': 0.20,
            'EMA': 0.15,
            'Volume': 0.15
        }
        # Track indicator performance
        self.indicator_performance = {
            'RSI': {'success': 0, 'total': 0, 'last_signal': None, 'last_price': None},
            'MACD': {'success': 0, 'total': 0, 'last_signal': None, 'last_price': None},
            'BB': {'success': 0, 'total': 0, 'last_signal': None, 'last_price': None},
            'EMA': {'success': 0, 'total': 0, 'last_signal': None, 'last_price': None},
            'Volume': {'success': 0, 'total': 0, 'last_signal': None, 'last_price': None}
        }
        self.min_weight = 0.05
        self.max_weight = 0.40
        self.last_weight_update = time.time()
        self.update_interval = 300  # Update weights every 5 minutes

    def analyze_indicators(self, indicators: Dict, current_price: float = None) -> Dict:
        """Analyze all indicators and provide a combined signal"""
        try:
            # Update indicator performance if we have price data
            if current_price:
                self._update_performance(current_price)

            # Update weights periodically
            if time.time() - self.last_weight_update > self.update_interval:
                self._adjust_weights()
                self.last_weight_update = time.time()

            analysis = {}
            recommendations = []
            total_weight = 0
            weighted_signal = 0
            active_indicators = 0

            for name, data in indicators.items():
                if not isinstance(data, dict):
                    continue

                indicator_analysis = self._analyze_single_indicator(name, data)
                if indicator_analysis:
                    analysis[name] = indicator_analysis
                    signal_value = self._signal_to_value(indicator_analysis['signal'])
                    
                    if signal_value is not None:
                        # Use dynamically adjusted weights
                        weight = self.indicator_weights.get(name, 0.1)
                        weighted_signal += signal_value * weight * indicator_analysis['reliability']
                        total_weight += weight * indicator_analysis['reliability']
                        active_indicators += 1
                        
                        # Store signal for performance tracking
                        if current_price and name in self.indicator_performance:
                            self.indicator_performance[name]['last_signal'] = signal_value
                            self.indicator_performance[name]['last_price'] = current_price
                        
                        if indicator_analysis.get('recommendations'):
                            recommendations.extend(indicator_analysis['recommendations'])

            if active_indicators == 0 or total_weight == 0:
                return self._default_analysis()

            # Calculate combined signal
            normalized_signal = weighted_signal / total_weight if total_weight > 0 else 0
            combined_signal = self._determine_combined_signal(normalized_signal, active_indicators)

            # Add current weights to the analysis
            return {
                "analysis": analysis,
                "combined_signal": combined_signal,
                "recommendations": list(set(recommendations)),
                "indicator_weights": self.indicator_weights,
                "performance_metrics": {
                    name: {
                        "success_rate": self._calculate_success_rate(name)
                    } for name in self.indicator_performance
                }
            }

        except Exception as e:
            logger.error(f"Error in indicator analysis: {e}")
            return self._default_analysis()

    def _update_performance(self, current_price: float):
        """Update indicator performance based on price movement"""
        for name, data in self.indicator_performance.items():
            if data['last_signal'] is not None and data['last_price'] is not None:
                price_change = (current_price - data['last_price']) / data['last_price']
                
                # Check if the signal was correct
                if (data['last_signal'] > 0 and price_change > 0) or \
                   (data['last_signal'] < 0 and price_change < 0):
                    data['success'] += 1
                
                data['total'] += 1
                data['last_signal'] = None
                data['last_price'] = None

    def _adjust_weights(self):
        """Dynamically adjust indicator weights based on performance"""
        total_success_rate = 0
        success_rates = {}

        # Calculate success rates
        for name, data in self.indicator_performance.items():
            success_rate = self._calculate_success_rate(name)
            success_rates[name] = success_rate
            total_success_rate += success_rate

        # Adjust weights based on relative performance
        if total_success_rate > 0:
            for name in self.indicator_weights:
                new_weight = (success_rates[name] / total_success_rate) 
                # Apply constraints
                new_weight = max(self.min_weight, min(self.max_weight, new_weight))
                self.indicator_weights[name] = round(new_weight, 2)

            # Normalize weights to sum to 1
            weight_sum = sum(self.indicator_weights.values())
            if weight_sum > 0:
                for name in self.indicator_weights:
                    self.indicator_weights[name] = round(self.indicator_weights[name] / weight_sum, 2)

            logger.info(f"Updated indicator weights: {json.dumps(self.indicator_weights)}")

    def _calculate_success_rate(self, indicator_name: str) -> float:
        """Calculate success rate for an indicator"""
        data = self.indicator_performance[indicator_name]
        if data['total'] == 0:
            return 0.5  # Default to neutral when no data
        return data['success'] / data['total']

    def _analyze_single_indicator(self, name: str, data: Dict) -> Dict:
        """Analyze a single indicator"""
        try:
            signal = data.get('signal', 'NEUTRAL')
            reliability = min(max(float(data.get('reliability', 0.5)), 0), 1)
            value = float(data.get('value', 0))
            
            analysis = {
                'signal': signal,
                'reliability': reliability,
                'value': value,
                'recommendations': []
            }

            # Add indicator-specific recommendations
            if name == 'RSI':
                if value > 70:
                    analysis['recommendations'].append("Consider taking profits - RSI overbought")
                elif value < 30:
                    analysis['recommendations'].append("Consider entry - RSI oversold")
                    
            elif name == 'MACD':
                if data.get('histogram_increasing'):
                    analysis['recommendations'].append("MACD momentum building")
                    
            elif name == 'BB':
                if data.get('price_at_upper'):
                    analysis['recommendations'].append("Price at upper band - watch for reversal")
                elif data.get('price_at_lower'):
                    analysis['recommendations'].append("Price at lower band - watch for bounce")

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing {name}: {e}")
            return None

    def _signal_to_value(self, signal: str) -> float:
        """Convert signal string to numeric value"""
        signal_values = {
            'STRONG_BUY': 1.0,
            'BUY': 0.5,
            'NEUTRAL': 0.0,
            'SELL': -0.5,
            'STRONG_SELL': -1.0
        }
        return signal_values.get(signal.upper(), 0.0)

    def _determine_combined_signal(self, normalized_signal: float, active_indicators: int) -> Dict:
        """Convert normalized signal to trading decision"""
        try:
            if active_indicators == 0:
                return {
                    "signal": "HOLD",
                    "confidence": 0.0,
                    "strength": 0.0,
                    "active_indicators": 0
                }
                
            # Adjust confidence based on number of active indicators
            base_confidence = min(active_indicators / 5, 1.0)  # Max confidence with 5+ indicators
            signal_strength = abs(normalized_signal) if normalized_signal != 0 else 0
            
            # Calculate final confidence with guard against zero
            confidence = base_confidence * signal_strength if base_confidence > 0 else 0

            # Determine signal type
            if normalized_signal > 0.2:
                signal = "BUY"
            elif normalized_signal < -0.2:
                signal = "SELL"
            else:
                signal = "HOLD"
                confidence *= 0.5  # Reduce confidence for HOLD signals

            return {
                "signal": signal,
                "confidence": round(min(max(confidence, 0), 1), 2),
                "strength": round(min(max(signal_strength, 0), 1), 2),
                "active_indicators": active_indicators
            }

        except Exception as e:
            logger.error(f"Error determining combined signal: {e}")
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "strength": 0.0,
                "active_indicators": 0
            }

    def _default_analysis(self) -> Dict:
        """Return default analysis when errors occur"""
        return {
            "analysis": {},
            "combined_signal": {
                "signal": "HOLD",
                "confidence": 0.0,
                "strength": 0.0,
                "active_indicators": 0
            },
            "recommendations": [],
            "indicator_weights": self.indicator_weights
        }
