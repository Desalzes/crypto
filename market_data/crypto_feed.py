import aiohttp
import pandas as pd
from datetime import datetime
import logging

class CryptoFeed:
    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3"
        self.logger = logging.getLogger(__name__)

    async def get_real_time_price(self, symbol: str):
        """Get current price for crypto pair"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.base_url}/ticker/price", params={"symbol": f"{symbol}USDT"}) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "symbol": symbol,
                            "price": float(data["price"]),
                            "timestamp": datetime.now().isoformat()
                        }
            except Exception as e:
                self.logger.error(f"Error fetching crypto price: {e}")
                return None

    async def get_klines(self, symbol: str, interval: str = "5m", limit: int = 100):
        """Get candlestick data"""
        async with aiohttp.ClientSession() as session:
            try:
                params = {
                    "symbol": f"{symbol}USDT",
                    "interval": interval,
                    "limit": limit
                }
                async with session.get(f"{self.base_url}/klines", params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if not data:
                            self.logger.warning(f"No klines data received for {symbol}")
                            return None
                            
                        df = pd.DataFrame(data, columns=[
                            "timestamp", "open", "high", "low", "close", "volume",
                            "close_time", "quote_volume", "trades", "taker_buy_volume",
                            "taker_buy_quote_volume", "ignore"
                        ])
                        
                        # Validate OHLC data
                        required_columns = ["open", "high", "low", "close"]
                        if not all(col in df.columns for col in required_columns):
                            self.logger.warning(f"Missing required OHLC columns for {symbol}")
                            return None
                            
                        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                        for col in ["open", "high", "low", "close", "volume"]:
                            df[col] = df[col].astype(float)
                            
                        # Validate data quality
                        if df.empty or len(df) < 10:  # Require at least 10 candles
                            self.logger.warning(f"Insufficient klines data for {symbol}: only {len(df)} candles received")
                            return None
                            
                        # Check for invalid values
                        if df[required_columns].isnull().any().any():
                            self.logger.warning(f"Found NULL values in OHLC data for {symbol}")
                            return None
                            
                        return df
                    else:
                        self.logger.warning(f"Failed to fetch klines data for {symbol}. Status: {response.status}")
                        return None
            except Exception as e:
                self.logger.error(f"Error fetching crypto klines: {e}")
                return None