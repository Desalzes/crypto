import logging
import asyncio
import os
import time
import json
from datetime import datetime
import aiohttp
from market_data.kraken_feed import KrakenFeed
from trading.paper_trader import PaperTrader
from trading.crypto_strategy import CryptoStrategy
from database.db_manager import DatabaseManager
from core.market_analyzer import IntegratedMarketAnalyzer
from utils.progress import trading_spinner
import sys

logger = logging.getLogger(__name__)

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
        self.market_analyzer = IntegratedMarketAnalyzer(config)
        self.batch_size = 4
        self.running = False
        self.last_balance = 1000.00
        self._http_session = None
        self.last_request_time = 0
        self.request_interval = 1.0
        self.loop_interval = 20
        self.trade_threshold = 0.45

    async def cleanup(self):
        self.running = False
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            self._http_session = None
        if hasattr(self, 'feed') and self.feed:
            await self.feed.close()

    async def run_trading_loop(self):
        self.running = True
        print(f"\nStarting trading bot with ${self.trader.get_portfolio_value({}):.2f}")
        
        try:
            while self.running:
                with trading_spinner():
                    pairs = await self.feed.get_active_pairs()
                    pairs = pairs[:14]
                    
                    for i in range(0, len(pairs), self.batch_size):
                        if not self.running:
                            break
                        batch = pairs[i:i + self.batch_size]
                        await self.analyze_batch(batch)
                        await asyncio.sleep(1)
                
                current_balance = self.trader.get_portfolio_value({})
                print(f"\rPortfolio Value: ${current_balance:.2f}")
                await self.update_trading_state(current_balance)
                
                sys.stdout.write(f"\rWaiting {self.loop_interval} seconds..." + " " * 20)
                sys.stdout.flush()
                await asyncio.sleep(self.loop_interval)
                
        except KeyboardInterrupt:
            print("\nShutting down...")
        except Exception as e:
            logger.error(f"Error in trading loop: {e}")
        finally:
            await self.cleanup()

    async def get_session(self):
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session

    async def rate_limit(self):
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.request_interval:
            await asyncio.sleep(self.request_interval - elapsed)
        self.last_request_time = now

    async def analyze_batch(self, pairs):
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

                    analysis = await self.market_analyzer.analyze_market(pair, ohlc_data[pair])
                    current_price = ticker_data[pair]['price']
                    
                    if analysis['summary']['primary_action'] != 'HOLD' and \
                       analysis['summary']['confidence'] >= self.trade_threshold:
                        
                        position_size = self.strategy.calculate_position_size(
                            self.trader.get_portfolio_value({}),
                            analysis['summary']['confidence'],
                            current_price
                        )
                        
                        if position_size > 0:
                            success = self.trader.place_order(
                                pair, 
                                analysis['summary']['primary_action'], 
                                position_size, 
                                current_price
                            )
                            
                            if success:
                                print(f"\r{analysis['summary']['primary_action']}: {position_size:.8f} {pair} @ ${current_price:.2f}")
                                sys.stdout.flush()
                    
                    position = self.trader.get_position(pair)
                    if position['quantity'] > 0:
                        profit_pct = ((current_price - position['avg_price']) / position['avg_price'] * 100)
                        if abs(profit_pct) >= 1.0:  # Only show significant P/L
                            print(f"\r{pair} Position: {profit_pct:+.2f}%")
                            sys.stdout.flush()
                        
        except Exception as e:
            logger.error(f"Analysis error: {e}")

    async def update_trading_state(self, balance: float):
        if balance != self.last_balance:
            state_file = 'trading_state.json'
            try:
                state = {
                    "balance": balance,
                    "history": [{
                        "balance": balance,
                        "timestamp": datetime.now().isoformat()
                    }]
                }
                
                with open(state_file, 'w') as f:
                    json.dump(state, f, indent=2)
                
                self.last_balance = balance
                
            except Exception as e:
                logger.error(f"Error updating trading state: {e}")
