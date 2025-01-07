import asyncio
import aiohttp
import pandas as pd
from datetime import datetime
import logging

class RealTimeFeed:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = 'https://www.alphavantage.co/query'
        self.price_history = {}

    async def get_real_time_price(self, symbol: str):
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol,
            'apikey': self.api_key
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'Global Quote' in data:
                        quote = data['Global Quote']
                        return {
                            'symbol': symbol,
                            'price': float(quote['05. price']),
                            'volume': float(quote['06. volume']),
                            'timestamp': datetime.now().isoformat(),
                            'change_percent': quote['10. change percent']
                        }
                return None

    async def get_intraday_data(self, symbol: str, interval: str = '5min'):
        params = {
            'function': 'TIME_SERIES_INTRADAY',
            'symbol': symbol,
            'interval': interval,
            'apikey': self.api_key,
            'outputsize': 'full'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    time_series_key = f'Time Series ({interval})'
                    if time_series_key in data:
                        df = pd.DataFrame.from_dict(data[time_series_key], orient='index')
                        df.columns = ['open', 'high', 'low', 'close', 'volume']
                        df = df.astype(float)
                        return df
                return None

    def update_price_history(self, symbol: str, price: float):
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append(price)
        if len(self.price_history[symbol]) > 100:
            self.price_history[symbol] = self.price_history[symbol][-100:]

    def get_price_history(self, symbol: str):
        return pd.Series(self.price_history.get(symbol, []))