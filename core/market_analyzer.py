import pandas as pd
from typing import Dict
import logging
from .pattern_recognition import PatternRecognizer
from .indicator_data import StructuredIndicatorData
from .market_context import MarketContextAnalyzer

logger = logging.getLogger(__name__)


class IntegratedMarketAnalyzer:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.pattern_recognizer = PatternRecognizer()
        self.market_context = MarketContextAnalyzer()

    def _calculate_position_size(self, portfolio_value: float, confidence: float, risk_level: str = 'HIGH') -> float:
        base_risk = {
            'LOW': 0.02,
            'MEDIUM': 0.015,
            'HIGH': 0.01
        }.get(risk_level, 0.01)

        position_size = portfolio_value * base_risk * confidence
        max_position = portfolio_value * 0.1
        return min(position_size, max_position)

    async def analyze_market(self, symbol: str, timeframe_data: Dict[str, pd.DataFrame]) -> Dict:
        try:
            logger.debug(f"Received timeframe data for {symbol}: {list(timeframe_data.keys())}")

            one_min_data = timeframe_data.get('1m')
            if one_min_data is None or one_min_data.empty:
                logger.error(f"No valid 1m data for {symbol}. Data: {one_min_data}")
                raise ValueError("No 1m timeframe data available")
            else:
                logger.debug(f"1m data for {symbol}: {one_min_data.head()}")

            # Validate columns in the 1m data
            required_columns = {'open', 'high', 'low', 'close', 'volume'}
            if not required_columns.issubset(one_min_data.columns):
                logger.error(f"Missing required columns in 1m data for {symbol}: {one_min_data.columns}")
                return self._default_analysis()

            # Process indicator data
            indicator_data = StructuredIndicatorData(one_min_data)
            indicators = indicator_data.get_combined_analysis()
            logger.debug(f"Indicators for {symbol}: {indicators}")

            # Analyze patterns
            patterns = self.pattern_recognizer.analyze_patterns(one_min_data)
            logger.debug(f"Patterns for {symbol}: {patterns}")

            # Analyze market context
            market_state = await self._analyze_market_context(timeframe_data)
            logger.debug(f"Market state for {symbol}: {market_state}")

            # Combine all analyses
            final_analysis = self._combine_analyses(indicators, patterns, market_state)

            if not self._validate_analysis(final_analysis):
                logger.warning(f"Invalid analysis for {symbol}. Returning default analysis.")
                return self._default_analysis()

            return final_analysis

        except Exception as e:
            logger.error(f"Error in market analysis for {symbol}: {str(e)}")
            return self._default_analysis()

    async def _analyze_market_context(self, timeframe_data: Dict[str, pd.DataFrame]) -> Dict:
        try:
            return self.market_context.analyze_market_context(timeframe_data)
        except Exception as e:
            logger.error(f"Error in market context analysis: {str(e)}")
            return self._default_market_context()

    def _combine_analyses(self, indicators: Dict, patterns: Dict, market_state: Dict) -> Dict:
        try:
            processed_indicators = {}
            for name, details in indicators.items():
                try:
                    processed_indicators[name] = {
                        'value': details.get('value', 0.0),
                        'signal': details.get('signal', 'NEUTRAL'),
                        'reliability': details.get('reliability', 0.0),
                        'warnings': details.get('warning_signals', [])
                    }
                except Exception as e:
                    logger.error(f"Error processing indicator {name}: {str(e)}")
                    continue

            combined_signal = self._calculate_combined_signal(processed_indicators, patterns, market_state)

            portfolio_value = 1000
            confidence = combined_signal.get('confidence', 0.0)
            risk_level = market_state.get('risk_level', 'HIGH')
            position_size = self._calculate_position_size(portfolio_value, confidence, risk_level)

            return {
                'summary': {
                    'primary_action': combined_signal.get('action', 'HOLD'),
                    'confidence': confidence,
                    'risk_level': risk_level
                },
                'market_context': market_state,
                'technical_indicators': processed_indicators,
                'patterns': patterns,
                'trading_parameters': {
                    'position_size': position_size,
                    'stop_loss': combined_signal.get('stop_loss'),
                    'take_profit': combined_signal.get('take_profit'),
                }
            }
        except Exception as e:
            logger.error(f"Error combining analyses: {str(e)}")
            return self._default_analysis()

    def _calculate_combined_signal(self, indicators: Dict, patterns: Dict, market_state: Dict) -> Dict:
        try:
            # Simple signal combination logic
            indicator_signals = [ind['signal'] for ind in indicators.values()]
            buy_signals = indicator_signals.count('BUY')
            sell_signals = indicator_signals.count('SELL')

            total_signals = len(indicator_signals)
            if total_signals == 0:
                return {'action': 'HOLD', 'confidence': 0.0}

            if buy_signals > sell_signals:
                action = 'BUY'
                confidence = buy_signals / total_signals
            elif sell_signals > buy_signals:
                action = 'SELL'
                confidence = sell_signals / total_signals
            else:
                action = 'HOLD'
                confidence = 0.0

            # Adjust confidence based on market state
            if market_state.get('volatility') == 'HIGH':
                confidence *= 0.8

            return {
                'action': action,
                'confidence': confidence,
                'stop_loss': None,  # Add stop loss calculation if needed
                'take_profit': None  # Add take profit calculation if needed
            }
        except Exception as e:
            logger.error(f"Error calculating combined signal: {str(e)}")
            return {'action': 'HOLD', 'confidence': 0.0}

    def _validate_analysis(self, analysis: Dict) -> bool:
        try:
            required_fields = ['summary', 'market_context', 'technical_indicators',
                               'patterns', 'trading_parameters']

            if not all(field in analysis for field in required_fields):
                return False

            summary = analysis['summary']
            if not all(key in summary for key in ['primary_action', 'confidence', 'risk_level']):
                return False

            if summary['primary_action'] not in ['BUY', 'SELL', 'HOLD']:
                return False
            if not isinstance(summary['confidence'], (int, float)):
                return False
            if not 0 <= summary['confidence'] <= 1:
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating analysis: {str(e)}")
            return False

    def _default_market_context(self) -> Dict:
        return {
            'regime': 'UNKNOWN',
            'volatility': 'HIGH',
            'liquidity': 'UNKNOWN',
            'trend_strength': 0.0,
            'key_levels': {},
            'recent_patterns': [],
            'risk_level': 'HIGH'
        }

    def _default_analysis(self) -> Dict:
        return {
            'summary': {
                'primary_action': 'HOLD',
                'confidence': 0.0,
                'risk_level': 'HIGH'
            },
            'market_context': self._default_market_context(),
            'technical_indicators': {},
            'patterns': {},
            'trading_parameters': {
                'position_size': 0.0,
                'stop_loss': None,
                'take_profit': None
            }
        }
