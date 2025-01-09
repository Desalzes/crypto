import asyncio
import aiohttp
import logging
import pandas as pd
import time
from typing import Dict, List, Optional

class KrakenFeed:
    def __init__(self, api_key: str = None, secret_key: str = None):
        self.api_url = "https://api.kraken.com"
        self.api_version = "0"
        self.session = None
        self.pairs_cache = {}
        self.ohlc_cache = {}
        self.volume_cache = None
        self.last_volume_update = 0
        self.last_ohlc_update = 0
        self.cache_duration = 5  # Cache for 5 seconds

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def get_active_pairs(self) -> List[str]:
        current_time = time.time()
        if self.volume_cache and current_time - self.last_volume_update < 300:
            return self.volume_cache[:20]

        try:
            ticker_data = await self._api_request('public/Ticker')
            volumes = [(pair, float(data['v'][1])) for pair, data in ticker_data.items()]
            sorted_pairs = [pair for pair, _ in sorted(volumes, key=lambda x: x[1], reverse=True)]
            self.volume_cache = sorted_pairs
            self.last_volume_update = current_time
            return sorted_pairs[:20]

        except Exception as e:
            logging.error(f"Error getting active pairs: {e}")
            return []

    async def get_ticker(self, pair: str) -> Optional[Dict]:
        try:
            result = await self._api_request('public/Ticker', {'pair': pair})
            if result and pair in result:
                ticker_data = result[pair]
                return {
                    'price': float(ticker_data['c'][0]),
                    'volume24h': float(ticker_data['v'][1]),
                    'change24h': (float(ticker_data['c'][0]) - float(ticker_data['o'])) / float(ticker_data['o']) * 100
                }
            return None
        except Exception as e:
            logging.error(f"Error getting ticker for {pair}: {str(e)}")
            return None

    async def get_all_timeframe_data(self, pair: str) -> Dict:
        timeframes = {'1m': 1, '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440}
        tasks = [self._get_timeframe_data(pair, tf_minutes) for tf_minutes in timeframes.values()]
        results = await asyncio.gather(*tasks)
        return dict(zip(timeframes.keys(), results))

    async def _get_timeframe_data(self, pair: str, interval: int) -> pd.DataFrame:
        try:
            data = await self._api_request('public/OHLC', {'pair': pair, 'interval': interval})
            if data and pair in data:
                ohlc_data = data[pair]
                df = pd.DataFrame(ohlc_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'])
                df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                df.set_index('timestamp', inplace=True)
                return df
            return pd.DataFrame()
        except Exception as e:
            logging.error(f"Error getting data for {pair}: {e}")
            return pd.DataFrame()

    async def _api_request(self, endpoint: str, data: dict = None) -> dict:
        if not self.session:
            self.session = aiohttp.ClientSession()
        if data is None:
            data = {}
        url = f"{self.api_url}/{self.api_version}/{endpoint}"
        try:
            async with self.session.get(url, params=data) as response:
                if response.status != 200:
                    return {}
                result = await response.json()
                return result.get('result', {})
        except Exception as e:
            logging.error(f"API request failed: {str(e)}")
            return {}