import logging
import asyncio
import os
import time
from market_data.kraken_feed import KrakenFeed
from trading.paper_trader import PaperTrader
from trading.crypto_strategy import CryptoStrategy
from database.db_manager import DatabaseManager
from core.analyzer import LLMAnalyzer
from tqdm import tqdm

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
        self.batch_size = 8
        self.running = False

    async def cleanup(self):
        self.running = False
        if hasattr(self, 'feed'):
            await self.feed.close()

    async def run_trading_loop(self):
        self.running = True
        print(f"\nStarting trading bot with ${self.trader.get_portfolio_value({}):.2f}")
        
        while self.running:
            try:
                pairs = await self.feed.get_active_pairs()
                print("\nAnalyzing Market Data:")
                print("-" * 50)
                
                for i in range(0, len(pairs), self.batch_size):
                    batch = pairs[i:i + self.batch_size]
                    await self.analyze_batch(batch)
                    if i + self.batch_size < len(pairs) and self.running:
                        await asyncio.sleep(1)
                
                if self.running:
                    print("-" * 50)
                    print(f"Portfolio Value: ${self.trader.get_portfolio_value({}):.2f}")
                    print("Waiting 30 seconds...")
                    await asyncio.sleep(30)
                    
            except Exception as e:
                logging.error(f"Error in trading loop: {e}")
                if self.running:
                    await asyncio.sleep(30)

    async def analyze_batch(self, pairs):
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
                if not analysis:
                    continue
                
                current_price = ticker_data[pair]['price']
                print(f"\n{pair} @ ${current_price:.2f} | Score: {analysis['summary']}")
                
                if analysis['action'] != 'HOLD':
                    position_size = self.strategy.calculate_position_size(
                        self.trader.get_portfolio_value({}),
                        analysis['confidence'],
                        current_price
                    )
                    print(f"Signal: {analysis['action']} | Confidence: {analysis['confidence']:.2f}")
                    
                    if position_size > 0:
                        success = self.trader.place_order(
                            pair, analysis['action'], position_size, current_price
                        )
                        if success:
                            print(f">> EXECUTED: {analysis['action']} {position_size:.8f} {pair}")
                
                position = self.trader.get_position(pair)
                if position['quantity'] > 0:
                    profit_pct = ((current_price - position['avg_price']) / 
                                position['avg_price'] * 100)
                    print(f"Position: {position['quantity']:.8f} ({profit_pct:+.2f}%)")
                    
        except Exception as e:
            logging.error(f"Error in batch analysis: {e}")