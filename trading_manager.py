import logging
import asyncio
import os
import time
import aiohttp
from tqdm import tqdm
from market_data.kraken_feed import KrakenFeed
from trading.paper_trader import PaperTrader
from trading.crypto_strategy import CryptoStrategy
from database.db_manager import DatabaseManager
from core.analyzer import LLMAnalyzer

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
        self.last_balance = 1000.00
        self._http_session = None
        self.last_request_time = 0
        self.request_interval = 1.0  # Seconds between requests

    async def get_session(self):
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session

    async def cleanup(self):
        """Clean up resources and close connections."""
        self.running = False
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            self._http_session = None
        if self.feed:
            await self.feed.close()

    async def rate_limit(self):
        """Implement rate limiting."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.request_interval:
            await asyncio.sleep(self.request_interval - elapsed)
        self.last_request_time = time.time()

    async def run_trading_loop(self):
        """Run the main trading loop with resource management."""
        self.running = True
        self.print_balance_header()
        logging.info("Starting crypto trading...")
        
        try:
            while self.running:
                pairs = await self.feed.get_active_pairs()
                pairs = pairs[:14]
                
                with tqdm(total=len(pairs), desc="Trading loop progress", 
                         bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}') as pbar:
                    
                    session = await self.get_session()
                    async with session:
                        for i in range(0, len(pairs), self.batch_size):
                            if not self.running:
                                break
                            
                            await self.rate_limit()
                            batch = pairs[i:i + self.batch_size]
                            await self.analyze_batch(batch)
                            pbar.update(len(batch))

                current_balance = self.trader.get_portfolio_value({})
                if abs(current_balance - self.last_balance) > 0.01:
                    print(f"\nBalance: ${current_balance:.2f} ({(current_balance-self.last_balance):+.2f})")
                    self.last_balance = current_balance
                
                print("\nTrading loop completed")
                if self.running:
                    await asyncio.sleep(30)
                    
        except Exception as e:
            logging.error(f"Error in trading loop: {e}")
        finally:
            await self.cleanup()

    async def analyze_batch(self, pairs):
        """Analyze pairs with resource management."""
        try:
            session = await self.get_session()
            async with session:
                ticker_data = dict(zip(pairs, await asyncio.gather(
                    *[self.feed.get_ticker(pair) for pair in pairs]
                )))
                
                await self.rate_limit()
                ohlc_data = dict(zip(pairs, await asyncio.gather(
                    *[self.feed.get_all_timeframe_data(pair) for pair in pairs]
                )))
                
                for pair in pairs:
                    if not ticker_data[pair] or not ohlc_data[pair]:
                        continue
                        
                    analysis = await self.strategy.analyze_all_timeframes(
                        pair, ticker_data[pair], ohlc_data[pair]
                    )
                    
                    if analysis and analysis['action'] != 'HOLD':
                        position_size = self.strategy.calculate_position_size(
                            self.trader.get_portfolio_value({}),
                            analysis['confidence'],
                            ticker_data[pair]['price']
                        )
                        
                        if position_size > 0:
                            success = self.trader.place_order(
                                pair, analysis['action'], position_size, 
                                ticker_data[pair]['price']
                            )
                            if success:
                                print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S')} - "
                                      f"{analysis['action']} - {pair} @ ${ticker_data[pair]['price']:.8f}")
                                
                    position = self.trader.get_position(pair)
                    if position['quantity'] > 0:
                        profit_pct = ((ticker_data[pair]['price'] - position['avg_price']) / 
                                    position['avg_price'] * 100)
                        if abs(profit_pct) >= 2.0:
                            print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S')} - "
                                  f"P/L Update - {pair}: {profit_pct:+.2f}%")
                        
        except Exception as e:
            logging.error(f"Analysis error: {e}")
