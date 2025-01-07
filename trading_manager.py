import logging
import asyncio
import os
import time
from datetime import datetime
from market_data.kraken_feed import KrakenFeed
from trading.paper_trader import PaperTrader
from trading.crypto_strategy import CryptoStrategy
from database.db_manager import DatabaseManager
from analysis.research_mode import ResearchMode
from analysis.llm.analyzer import LLMAnalyzer
from utils.progress import progress_spinner

class TradingManager:
    def __init__(self, config: dict, db: DatabaseManager, mode: str):
        self.config = config
        self.db = db
        self.mode = mode
        self.feed = KrakenFeed(
            api_key=os.getenv('KRAKEN_API_KEY'),
            secret_key=os.getenv('KRAKEN_SECRET_KEY')
        )
        self.trader = PaperTrader(initial_balance=1000)
        self.strategy = CryptoStrategy(db)
        self.batch_size = 4
        self.running = False

    async def cleanup(self):
        """Clean up and close connections."""
        self.running = False
        if hasattr(self, 'feed'):
            await self.feed.close()

    async def stop_trading(self):
        """Stop the trading loop."""
        self.running = False
        await self.cleanup()

    async def run_llm_review(self):
        """Run LLM review of indicators with detailed analysis."""
        logging.info("\n-----------------")
        logging.info(f"Balance: ${self.trader.get_portfolio_value({}):.2f}")
        logging.info("-----------------")
        
        try:
            with progress_spinner("Fetching market data"):
                pairs = await self.feed.get_active_pairs()
                pairs = pairs[:5]  # Analyze top 5 pairs
            
            analyzer = LLMAnalyzer(self.config)
            
            for idx, pair in enumerate(pairs, 1):
                try:
                    pair_message = f"Analyzing {pair} ({idx}/{len(pairs)})"
                    with progress_spinner(pair_message):
                        ticker, ohlcv = await self.get_market_data_with_retry(pair)
                        
                        if ticker is None or ohlcv is None:
                            logging.warning(f"Could not get valid data for {pair}")
                            continue
                        
                        analysis = await self.strategy.analyze_all_timeframes(
                            pair, ticker, ohlcv
                        )
                        
                        if not analysis:
                            logging.warning(f"No valid analysis generated for {pair}")
                            continue
                        
                        market_data = {
                            'symbol': pair,
                            'price': ticker['price'],
                            'volume': ticker.get('volume24h', 'N/A'),
                            'signals': analysis.get('signals', {}),
                            'technical_analysis': analysis,
                            'profit': self.trader.get_position(pair).get('profit_loss', 0)
                        }
                        
                        llm_analysis = await analyzer.analyze_indicators(market_data)
                        
                        if not llm_analysis:
                            logging.warning(f"No LLM analysis generated for {pair}")
                            continue
                        
                        self._print_analysis(pair, llm_analysis)
                        
                        if self._should_apply_recommendations(llm_analysis):
                            await self._apply_recommendations(llm_analysis)
                        
                        await asyncio.sleep(2)
                        
                except Exception as e:
                    logging.error(f"Error analyzing {pair}: {e}")
                    continue
            
            logging.info("\nLLM review completed successfully.")
                    
        except Exception as e:
            logging.error(f"Error in LLM review: {e}")
            return

    async def get_market_data_with_retry(self, pair, max_retries=3, delay=2):
        """Get market data with retry logic."""
        for attempt in range(max_retries):
            try:
                ticker = await self.feed.get_ticker(pair)
                if not ticker:
                    logging.warning(f"No ticker data for {pair}, attempt {attempt + 1}/{max_retries}")
                    await asyncio.sleep(delay)
                    continue

                ohlcv = await self.feed.get_all_timeframe_data(pair)
                if not ohlcv:
                    logging.warning(f"No OHLCV data for {pair}, attempt {attempt + 1}/{max_retries}")
                    await asyncio.sleep(delay)
                    continue

                return ticker, ohlcv

            except Exception as e:
                logging.error(f"Error fetching data for {pair}: {e}, attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                continue

        return None, None

    def _print_analysis(self, pair: str, analysis: dict):
        """Print formatted LLM analysis results."""
        logging.info(f"\n=== Analysis for {pair} ===")
        
        logging.info("\nIndicator Analysis:")
        for indicator, stats in analysis.get('indicator_analysis', {}).items():
            logging.info(f"\n{indicator}:")
            logging.info(f"Reliability: {stats.get('reliability', 0):.2f}")
            logging.info(f"Suggested Changes: {stats.get('suggested_changes', 'None')}")
            if stats.get('concerns'):
                logging.info("Concerns:")
                for concern in stats['concerns']:
                    logging.info(f"- {concern}")
        
        logging.info("\nStrategy Adjustments:")
        for adjustment in analysis.get('strategy_adjustments', []):
            logging.info(f"- {adjustment}")
        
        logging.info(f"\nSummary: {analysis.get('summary', 'No summary available')}")

    async def _apply_recommendations(self, analysis: dict):
        """Apply recommended strategy adjustments."""
        logging.info("\nApplying recommended adjustments...")
        
        try:
            applied_changes = []
            
            for indicator, stats in analysis.get('indicator_analysis', {}).items():
                if stats.get('reliability', 0) > 0.7:
                    current_weight = self.strategy.get_indicator_weight(indicator)
                    new_weight = min(current_weight * 1.1, 1.0)
                    self.strategy.set_indicator_weight(indicator, new_weight)
                    applied_changes.append(
                        f"Increased {indicator} weight to {new_weight:.2f}"
                    )
                elif stats.get('reliability', 0) < 0.3:
                    current_weight = self.strategy.get_indicator_weight(indicator)
                    new_weight = max(current_weight * 0.9, 0.1)
                    self.strategy.set_indicator_weight(indicator, new_weight)
                    applied_changes.append(
                        f"Decreased {indicator} weight to {new_weight:.2f}"
                    )
            
            if applied_changes:
                logging.info("\nSuccessfully applied changes:")
                for change in applied_changes:
                    logging.info(f"- {change}")
            else:
                logging.info("No changes were applied")
                
        except Exception as e:
            logging.error(f"Error applying recommendations: {e}")

    def _should_apply_recommendations(self, analysis: dict) -> bool:
        """Determine if recommendations should be automatically applied."""
        has_adjustments = len(analysis.get('strategy_adjustments', [])) > 0
        
        reliable_indicators = [
            ind for ind, stats in analysis.get('indicator_analysis', {}).items()
            if stats.get('reliability', 0) > 0.7
        ]
        
        return has_adjustments and len(reliable_indicators) > 0

    async def run_trading_loop(self):
        """Run the main trading loop."""
        self.running = True
        while self.running:
            try:
                loop_start = time.perf_counter()
                total_balance = self.trader.get_portfolio_value({})
                logging.info(f"\nBalance: ${total_balance:.2f}")
                
                pairs = await self.feed.get_active_pairs()
                pairs = pairs[:14]
                
                for i in range(0, len(pairs), self.batch_size):
                    batch = pairs[i:i + self.batch_size]
                    await self.analyze_batch(batch)
                    if i + self.batch_size < len(pairs) and self.running:
                        await asyncio.sleep(1)
                
                loop_time = time.perf_counter() - loop_start
                logging.info(f"Trading loop completed in {loop_time:.3f}s")
                
                if self.running:
                    await asyncio.sleep(60)
            except Exception as e:
                logging.error(f"Error in trading loop: {e}")
                if self.running:
                    await asyncio.sleep(60)

    async def analyze_batch(self, pairs):
        """Analyze a batch of trading pairs."""
        try:
            ticker_tasks = [self.feed.get_ticker(pair) for pair in pairs]
            tickers = await asyncio.gather(*ticker_tasks)
            ticker_data = dict(zip(pairs, tickers))

            ohlc_tasks = [self.feed.get_all_timeframe_data(pair) for pair in pairs]
            ohlc_data = dict(zip(pairs, await asyncio.gather(*ohlc_tasks)))
            
            analysis_tasks = [
                self.strategy.analyze_all_timeframes(pair, ticker_data[pair], ohlc_data[pair])
                for pair in pairs if ticker_data[pair] and ohlc_data[pair]
            ]
            analyses = await asyncio.gather(*analysis_tasks)
            
            for pair, analysis in zip(pairs, analyses):
                if analysis['action'] != 'HOLD':
                    position_size = self.strategy.calculate_position_size(
                        self.trader.get_portfolio_value({}),
                        analysis['confidence'],
                        ticker_data[pair]['price']
                    )
                    if position_size > 0:
                        success = self.trader.place_order(
                            pair, analysis['action'], position_size, ticker_data[pair]['price']
                        )
                        if success:
                            logging.info(f"{pair} {analysis['action']} {analysis['summary']}")
                
                position = self.trader.get_position(pair)
                if position['quantity'] > 0:
                    profit_pct = ((ticker_data[pair]['price'] - position['avg_price']) / 
                                position['avg_price'] * 100)
                    logging.info(
                        f"{pair} ${ticker_data[pair]['price']:.8f} | "
                        f"Pos: {position['quantity']:.8f} ({profit_pct:+.2f}%)"
                    )
                else:
                    logging.info(f"{pair} ${ticker_data[pair]['price']:.8f}")
                    
        except Exception as e:
            logging.error(f"Error in batch analysis: {e}")
