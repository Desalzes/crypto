import pandas as pd
from typing import Dict, Optional
import logging
from .pattern_recognition import PatternRecognizer
from .indicator_data import StructuredIndicatorData
from .market_context import MarketContextAnalyzer
from .analyzer import LLMAnalyzer
from .llm_indicator_analyzer import LLMIndicatorAnalyzer

logger = logging.getLogger(__name__)

class IntegratedMarketAnalyzer:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.pattern_recognizer = PatternRecognizer()
        self.market_context = MarketContextAnalyzer()
        self.llm_analyzer = LLMAnalyzer(config)
        self.indicator_analyzer = LLMIndicatorAnalyzer()

    async def analyze_market(self, symbol: str, timeframe_data: Dict[str, pd.DataFrame]) -> Dict:
        """Perform comprehensive market analysis"""
        try:
            # Get structured indicator data
            logger.info(f"Analyzing indicators for {symbol}")
            one_min_data = timeframe_data.get('1m')
            if one_min_data is None or one_min_data.empty:
                raise ValueError("No 1m timeframe data available")
            
            indicator_data = StructuredIndicatorData(one_min_data)
            indicators = indicator_data.get_combined_analysis()

            # Get LLM indicator analysis
            logger.info("Performing LLM indicator analysis")
            llm_indicator_analysis = self.indicator_analyzer.analyze_indicators(indicators)

            # Get pattern recognition
            logger.info("Analyzing patterns")
            patterns = self.pattern_recognizer.analyze_patterns(one_min_data)

            # Get market context
            logger.info("Analyzing market context")
            market_state = await self._analyze_market_context(timeframe_data)

            # Prepare market data for LLM analysis
            market_data = self._prepare_market_data(
                symbol, indicators, patterns, market_state, timeframe_data
            )

            # Get LLM analysis
            logger.info("Getting LLM analysis")
            llm_analysis = await self.llm_analyzer.analyze_indicators(market_data)

            # Combine all analyses
            final_analysis = self._combine_analyses(
                indicators, 
                patterns, 
                market_state, 
                llm_analysis,
                llm_indicator_analysis
            )

            # Validate final analysis
            if not self._validate_analysis(final_analysis):
                logger.warning(f"Analysis validation failed for {symbol}")
                return self._default_analysis()

            return final_analysis

        except Exception as e:
            logger.error(f"Error in market analysis: {str(e)}")
            return self._default_analysis()

    async def _analyze_market_context(self, timeframe_data: Dict[str, pd.DataFrame]) -> Dict:
        """Analyze market context with error handling"""
        try:
            return self.market_context.analyze_market_context(timeframe_data)
        except Exception as e:
            logger.error(f"Error in market context analysis: {str(e)}")
            return self._default_market_context()

    def _prepare_market_data(self, symbol: str, indicators: Dict, 
                           patterns: Dict, market_state: Dict,
                           timeframe_data: Dict[str, pd.DataFrame]) -> Dict:
        """Prepare market data for LLM analysis"""
        try:
            summaries = {}
            for tf, df in timeframe_data.items():
                if not df.empty:
                    summaries[tf] = self._extract_timeframe_summary(df)

            return {
                'symbol': symbol,
                'technical_analysis': {
                    'indicators': indicators,
                    'patterns': patterns,
                    'market_state': market_state
                },
                'timeframes': summaries,
                'current_price': timeframe_data['1m']['close'].iloc[-1] if '1m' in timeframe_data else None
            }
        except Exception as e:
            logger.error(f"Error preparing market data: {str(e)}")
            return {
                'symbol': symbol,
                'technical_analysis': {},
                'timeframes': {},
                'current_price': None
            }

    def _extract_timeframe_summary(self, df: pd.DataFrame) -> Dict:
        """Extract key metrics from a timeframe"""
        try:
            if df.empty:
                return {}

            latest = df.iloc[-1]
            lookback = min(10, len(df))
            
            return {
                'close': float(latest['close']),
                'high': float(latest['high']),
                'low': float(latest['low']),
                'volume': float(latest['volume']),
                'volatility': float(df['close'].pct_change().std()),
                'trend': 'up' if df['close'].iloc[-1] > df['close'].iloc[-lookback] else 'down'
            }
        except Exception as e:
            logger.error(f"Error extracting timeframe summary: {str(e)}")
            return {}

    def _combine_analyses(self, indicators: Dict, patterns: Dict, 
                         market_state: Dict, llm_analysis: Dict,
                         llm_indicator_analysis: Dict) -> Dict:
        """Combine all analyses with error handling"""
        try:
            # Process indicators
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

            # Extract LLM insights
            recommendation = llm_analysis.get('execution_signals', {})
            risk_assessment = llm_analysis.get('risk_metrics', {})

            # Merge LLM indicator analysis with recommendation
            primary_action = recommendation.get('primary_action', 'HOLD')
            confidence = recommendation.get('confidence', 0.0)
            
            # If LLM indicator analysis suggests a strong signal, consider it
            if llm_indicator_analysis["combined_signal"]["confidence"] > confidence:
                primary_action = llm_indicator_analysis["combined_signal"]["signal"]
                confidence = llm_indicator_analysis["combined_signal"]["confidence"]

            return {
                'summary': {
                    'primary_action': primary_action,
                    'confidence': confidence,
                    'risk_level': risk_assessment.get('trade_risk', 'HIGH'),
                    'indicator_confidence': llm_indicator_analysis["combined_signal"]["confidence"]
                },
                'market_context': {
                    'regime': market_state.get('regime', 'UNKNOWN'),
                    'volatility': market_state.get('volatility', 'HIGH'),
                    'liquidity': market_state.get('liquidity', 'UNKNOWN'),
                    'trend_strength': market_state.get('trend_strength', 0.0),
                    'risk_level': risk_assessment.get('trade_risk', 'HIGH')
                },
                'technical_indicators': processed_indicators,
                'patterns': patterns,
                'llm_analysis': {
                    'indicator_insights': llm_analysis.get('indicator_analysis', {}),
                    'pattern_insights': llm_analysis.get('price_action', {}),
                    'risk_factors': risk_assessment.get('risk_factors', []),
                    'indicator_analysis': llm_indicator_analysis["analysis"],
                    'indicator_recommendations': llm_indicator_analysis["recommendations"]
                },
                'trading_parameters': {
                    'position_size': recommendation.get('position_size_modifier', 0.0),
                    'stop_loss': recommendation.get('stop_loss'),
                    'take_profit': recommendation.get('take_profit', []),
                    'timeframe_validity': recommendation.get('timeframe_validity')
                }
            }
        except Exception as e:
            logger.error(f"Error combining analyses: {str(e)}")
            return self._default_analysis()

    def _validate_analysis(self, analysis: Dict) -> bool:
        """Validate the analysis output"""
        try:
            required_fields = ['summary', 'market_context', 'technical_indicators', 
                             'patterns', 'llm_analysis', 'trading_parameters']
            
            # Check main structure
            if not all(field in analysis for field in required_fields):
                return False

            # Validate summary fields
            summary = analysis['summary']
            if not all(key in summary for key in ['primary_action', 'confidence', 'risk_level']):
                return False

            # Validate action and confidence
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
        """Return default market context"""
        return {
            'regime': 'UNKNOWN',
            'volatility': 'HIGH',
            'liquidity': 'UNKNOWN',
            'trend_strength': 0.0,
            'key_levels': {},
            'recent_patterns': [],
            'risk_level': 'HIGH',
            'trading_suggestions': {}
        }

    def _default_analysis(self) -> Dict:
        """Return default analysis when errors occur"""
        return {
            'summary': {
                'primary_action': 'HOLD',
                'confidence': 0.0,
                'risk_level': 'HIGH',
                'indicator_confidence': 0.0
            },
            'market_context': self._default_market_context(),
            'technical_indicators': {},
            'patterns': {},
            'llm_analysis': {
                'indicator_analysis': {},
                'indicator_recommendations': []
            },
            'trading_parameters': {
                'position_size': 0.0,
                'stop_loss': None,
                'take_profit': None,
                'timeframe_validity': None
            }
        }