import aiohttp
import time
import logging
import pandas as pd
from typing import Dict, List, Optional
from market_data.base_feed import MarketDataFeed
from database.db_manager import DatabaseManager
import os
import json

logger = logging.getLogger(__name__)

class KrakenFeed(MarketDataFeed):
    def __init__(self, api_key: str = None, secret_key: str = None):
        self.api_key = api_key
        self.secret_key = secret_key
        self.api_url = "https://api.kraken.com"
        self.api_version = "0"
        self.session = None
        self.db = DatabaseManager()
        self.pairs = {}
        self.reverse_pairs = {}
        self.cached_volume_rankings = None
        self.last_ranking_update = 0
        
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(script_dir, 'config', 'crypto_pairs.json')
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                self.pairs = {p['db']: p['exchange'] for p in config['kraken_pairs']}
                self.reverse_pairs = {v: k for k, v in self.pairs.items()}
        except Exception as e:
            logger.error(f"Error loading pair mappings: {e}")

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def get_volume_rankings(self) -> List[str]:
        current_time = time.time()
        if self.cached_volume_rankings and current_time - self.last_ranking_update < 300:
            return self.cached_volume_rankings

        try:
            ticker_data = await self._api_request('public/Ticker')
            volumes = []
            for kraken_pair, data in ticker_data.items():
                if kraken_pair in self.reverse_pairs:
                    db_pair = self.reverse_pairs[kraken_pair]
                    volume = float(data['v'][1])  # 24h volume
                    volumes.append((db_pair, volume))

            sorted_pairs = [pair for pair, _ in sorted(volumes, key=lambda x: x[1], reverse=True)]
            self.cached_volume_rankings = sorted_pairs
            self.last_ranking_update = current_time
            return sorted_pairs

        except Exception as e:
            logger.error(f"Error getting volume rankings: {e}")
            return list(self.pairs.keys())[:10]

    async def get_ticker(self, pair: str) -> Optional[Dict]:
        try:
            exchange_pair = self.pairs.get(pair, pair)
            result = await self._api_request('public/Ticker', {'pair': exchange_pair})
            
            if result and exchange_pair in result:
                ticker_data = result[exchange_pair]
                return {
                    'price': float(ticker_data['c'][0]),
                    'volume24h': float(ticker_data['v'][1]),
                    'change24h': (float(ticker_data['c'][0]) - float(ticker_data['o'])) 
                               / float(ticker_data['o']) * 100
                }
            return None
        except Exception as e:
            logger.error(f"Error getting ticker for {pair}: {str(e)}")
            return None

    async def get_all_timeframe_data(self, pair: str) -> Dict:
        timeframes = {
            '1m': 1, '5m': 5, '15m': 15, 
            '1h': 60, '4h': 240, '1d': 1440
        }
        
        result = {}
        exchange_pair = self.pairs.get(pair, pair)
            
        for tf_name, tf_minutes in timeframes.items():
            try:
                data = await self._api_request('public/OHLC', {
                    'pair': exchange_pair,
                    'interval': tf_minutes
                })
                
                if data and exchange_pair in data:
                    ohlc_data = data[exchange_pair]
                    df = pd.DataFrame(ohlc_data, columns=[
                        'timestamp', 'open', 'high', 'low', 'close', 
                        'vwap', 'volume', 'count'
                    ])
                    
                    df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                    df.set_index('timestamp', inplace=True)
                    
                    perf = self.db.get_best_indicators(pair, tf_name)
                    df.attrs['performance'] = perf
                    
                    result[tf_name] = df
                else:
                    result[tf_name] = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
            except Exception as e:
                logger.error(f"Error getting {tf_name} data for {pair}: {e}")
                result[tf_name] = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
                
        return result

    async def get_active_pairs(self) -> List[str]:
        try:
            ranked_pairs = await self.get_volume_rankings()
            return ranked_pairs[:10]  # Return top 10 by volume
        except Exception as e:
            logger.error(f"Error getting active pairs: {e}")
            return list(self.pairs.keys())[:10]

    async def _api_request(self, endpoint: str, data: dict = None) -> dict:
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        if data is None:
            data = {}
            
        url = f"{self.api_url}/{self.api_version}/{endpoint}"
        
        try:
            async with self.session.get(url, params=data) as response:
                if response.status != 200:
                    logger.error(f"API request failed with status {response.status}")
                    return {}
                result = await response.json()
                
                if 'error' in result and result['error']:
                    logger.error(f"Kraken API error: {result['error']}")
                    return {}
                    
                return result.get('result', {})
                
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            return {}