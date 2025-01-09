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
from database import DatabaseManager

logger = logging.getLogger(__name__)

class TradingManager:
    def __init__(self, config: dict, db: DatabaseManager, mode: str = "crypto"):
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
        self.request_interval = 1.0
        self.loop_interval = 20
        self.trade_threshold = 0.45