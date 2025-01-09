import asyncio
import os
import time
import json
from datetime import datetime
import aiohttp
from tqdm import tqdm
from market_data.kraken_feed import KrakenFeed
from trading.paper_trader import PaperTrader
from trading.crypto_strategy import CryptoStrategy
from core.market_analyzer import IntegratedMarketAnalyzer

class TradingManager:
    def __init__(self, config: dict, mode: str):
        self.config = config
        self.mode = mode
        self.feed = KrakenFeed()
        self.trader = PaperTrader(initial_balance=1000)
        self.strategy = CryptoStrategy()
        self.market_analyzer = IntegratedMarketAnalyzer(config)
        self.running = False
        self.last_balance = 1000.00
        self._http_session = None
        self.last_request_time = 0
        self.request_interval = 1.0
        self.loop_interval = 5
        self.trade_threshold = 0.45
        self.progress_bar = None

    async def run_trading_loop(self):
        self.running = True
        print(f"\nStarting trading bot with ${self.trader.get_portfolio_value({}):.2f}")
        
        while self.running:
            try:
                pairs = await self.feed.get_active_pairs()
                pairs = pairs[:14]
                await self.analyze_batch(pairs)
                current_balance = self.trader.get_portfolio_value({})
                
                if abs(current_balance - self.last_balance) >= 0.01:
                    await self.update_trading_state(current_balance)
                
                if self.running:
                    await asyncio.sleep(self.loop_interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
                if self.running:
                    await asyncio.sleep(self.loop_interval)

    async def analyze_batch(self, pairs):
        session = await self.get_session()
        async with session:
            ticker_data = dict(zip(pairs, await asyncio.gather(
                *[self.feed.get_ticker(pair) for pair in pairs]
            )))
            
            await self.rate_limit()
            ohlc_data = dict(zip(pairs, await asyncio.gather(
                *[self.feed.get_all_timeframe_data(pair) for pair in pairs]
            )))
            
            if self.progress_bar is None:
                self.progress_bar = tqdm(total=len(pairs), desc="Analyzing markets", leave=True)
            else:
                self.progress_bar.reset(total=len(pairs))
                
            for pair in pairs:
                if not ticker_data[pair] or not ohlc_data[pair]:
                    self.progress_bar.update(1)
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
                            print(f"\n{analysis['summary']['primary_action']}: {position_size:.8f} {pair} @ ${current_price:.2f}")
                
                position = self.trader.get_position(pair)
                if position['quantity'] > 0:
                    profit_pct = ((current_price - position['avg_price']) / position['avg_price'] * 100)
                    if abs(profit_pct) >= 1.0:
                        print(f"\n{pair} Position: {profit_pct:+.2f}%")
                    
                self.progress_bar.update(1)

    async def cleanup(self):
        self.running = False
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
        if hasattr(self, 'feed'):
            await self.feed.close()
        if self.progress_bar:
            self.progress_bar.close()

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

    async def update_trading_state(self, balance: float):
        if balance != self.last_balance:
            state_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'trading_state.json')
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
                print(f"Error updating state: {e}")
