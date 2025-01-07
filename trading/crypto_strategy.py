import pandas as pd
import numpy as np
from typing import Dict, Tuple
from analysis.indicators import Indicators
from database.db_manager import DatabaseManager
from analysis.backtester import Backtester
from analysis.ml_classifier import MarketClassifier
import logging
import asyncio

class CryptoStrategy:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.min_trade_amount = 10
        self.backtester = Backtester()
        self.classifier = MarketClassifier()
        self.indicator_weights = {
            'RSI': 0.5,
            'MACD': 0.5,
            'Bollinger Bands': 0.5
        }

    async def analyze_all_timeframes(self, pair: str, ticker: dict, ohlcv_data: dict) -> Dict:
        """Analyze all timeframes for a trading pair."""
        try:
            # Get historical performance from database
            indicators_performance = {}
            for timeframe in ['5m', '15m', '1h']:
                performance = self.db.get_best_indicators(pair, timeframe)
                if performance:
                    indicators_performance[timeframe] = performance

            # Validate OHLCV data
            if not ohlcv_data or not ticker:
                logging.warning(f"Missing data for {pair}")
                return self._create_hold_signal(pair)

            # Get ML prediction if available
            try:
                ml_prob = self.classifier.predict(ohlcv_data.get('15m', pd.DataFrame()))
            except Exception as e:
                logging.error(f"ML prediction error: {e}")
                ml_prob = 0.5

            # Calculate technical indicators
            signals = {}
            for timeframe, data in ohlcv_data.items():
                if isinstance(data, pd.DataFrame) and not data.empty:
                    try:
                        signals[timeframe] = Indicators.calculate_all(data, timeframe)
                    except Exception as e:
                        logging.error(f"Error calculating indicators for {timeframe}: {e}")
                        continue

            if not signals:
                logging.warning(f"No valid signals calculated for {pair}")
                return self._create_hold_signal(pair)

            # Calculate combined score using historical performance
            score = self._calculate_combined_score(
                signals=signals,
                ticker=ticker,
                pair=pair,
                ml_prob=ml_prob,
                performance=indicators_performance
            )

            # Make trading decision
            decision = self._make_decision(score, pair)

            # Log analysis results
            self._log_analysis(pair, decision, signals)

            return decision

        except Exception as e:
            logging.error(f"Error in analyze_all_timeframes for {pair}: {e}")
            return self._create_hold_signal(pair)

    def _calculate_combined_score(self, signals: Dict, ticker: dict, 
                                pair: str, ml_prob: float,
                                performance: Dict) -> tuple:
        """Calculate combined score using historical performance."""
        score = 0
        indicators_used = []

        # Add ML score
        ml_score = (ml_prob - 0.5) * 2 * 0.4
        score += ml_score
        if abs(ml_score) > 0.1:
            indicators_used.append(f"ML{'+'if ml_score>0 else'-'}")

        # Process each timeframe
        for timeframe, indicators in signals.items():
            # Get timeframe weight from historical performance
            base_weight = self._get_timeframe_weight(timeframe)
            tf_performance = performance.get(timeframe, {})
            
            # RSI + MACD
            if tf_performance.get('RSI', 0) > 0.5 and tf_performance.get('MACD', 0) > 0.5:
                rsi_macd = self._check_rsi_macd(indicators)
                adj_weight = base_weight * max(tf_performance.get('RSI', 0.5), 
                                            tf_performance.get('MACD', 0.5))
                score += rsi_macd * adj_weight
                if rsi_macd != 0:
                    indicators_used.append(
                        f"{timeframe}({'RSI+MACD' if rsi_macd > 0 else 'RSI-MACD'})"
                    )

            # Bollinger Bands
            if tf_performance.get('BB', 0) > 0.4:
                bb = self._check_bollinger(indicators, ticker['price'])
                adj_weight = base_weight * tf_performance.get('BB', 0.5)
                score += bb * adj_weight
                if bb != 0:
                    indicators_used.append(f"{timeframe}(BB{'+-'[bb<0]})")

            # EMAs
            if tf_performance.get('EMA', 0) > 0.4:
                ema = self._check_ema(indicators)
                adj_weight = base_weight * tf_performance.get('EMA', 0.5)
                score += ema * adj_weight
                if ema != 0:
                    indicators_used.append(f"{timeframe}(EMA{'+-'[ema<0]})")

        return score, indicators_used

    def _create_hold_signal(self, pair: str) -> Dict:
        """Create a hold signal."""
        return {
            'action': 'HOLD',
            'confidence': 0,
            'summary': '',
            'indicators': []
        }

    def _log_analysis(self, pair: str, decision: Dict, signals: Dict):
        """Log analysis results to database."""
        try:
            # Log individual indicator performance
            for timeframe, indicators in signals.items():
                for indicator, value in indicators.items():
                    if isinstance(value, (int, float)):
                        self.db.update_indicator_performance(
                            pair=pair,
                            timeframe=timeframe,
                            indicator=indicator,
                            success=1 if decision['action'] != 'HOLD' else 0.5,
                            total=1
                        )
        except Exception as e:
            logging.error(f"Error logging analysis: {e}")

    def calculate_position_size(self, portfolio_value: float, confidence: float, price: float) -> float:
        """Calculate the position size based on portfolio value and confidence."""
        if confidence < 0.2:
            return 0
        position_usd = portfolio_value * 0.02 * confidence
        if position_usd < self.min_trade_amount:
            return 0
        return round(position_usd / price, 8)

    def _make_decision(self, score_data: tuple, pair: str) -> Dict:
        """Make trading decision based on score."""
        score, indicators = score_data
        
        if abs(score) < 1:
            return {
                'action': 'HOLD',
                'confidence': 0,
                'summary': ' '.join(indicators),
                'indicators': indicators
            }
            
        return {
            'action': 'BUY' if score > 0 else 'SELL',
            'confidence': min(abs(score)/3, 1),
            'summary': ' '.join(indicators),
            'indicators': indicators
        }

    @staticmethod
    def _get_timeframe_weight(timeframe: str) -> float:
        """Get weight for timeframe."""
        weights = {'1m': 0.4, '5m': 0.35, '15m': 0.25}
        return weights.get(timeframe, 0.3)

    @staticmethod
    def _check_rsi_macd(indicators: Dict) -> float:
        """Check RSI and MACD signals."""
        if indicators['rsi'] < 30 and indicators['macd'] > indicators['macd_signal']:
            return 1.0
        elif indicators['rsi'] > 70 and indicators['macd'] < indicators['macd_signal']:
            return -1.0
        return 0

    @staticmethod
    def _check_bollinger(indicators: Dict, price: float) -> float:
        """Check Bollinger Bands signals."""
        if price < indicators['bb_lower']:
            return 0.5
        elif price > indicators['bb_upper']:
            return -0.5
        return 0

    @staticmethod
    def _check_ema(indicators: Dict) -> float:
        """Check EMA signals."""
        if indicators['ema_short'] > indicators['ema_long']:
            return 0.3
        elif indicators['ema_short'] < indicators['ema_long']:
            return -0.3
        return 0

    @staticmethod
    def _check_ichimoku(indicators: Dict) -> float:
        """Check Ichimoku signals."""
        if indicators['tenkan_sen'] > indicators['kijun_sen']:
            return 0.2
        elif indicators['tenkan_sen'] < indicators['kijun_sen']:
            return -0.2
        return 0