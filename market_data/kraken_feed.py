import asyncio
import aiohttp
import logging
import pandas as pd
import time
import json
import hmac
import base64
import hashlib
import urllib.parse
from typing import Dict, List, Optional, Callable
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class KrakenFeed:
    def __init__(self, api_key: str = None, secret_key: str = None):
        self.api_url = "https://api.kraken.com"
        self.ws_url = "wss://ws.kraken.com"
        self.api_key = api_key
        self.secret_key = secret_key
        self.session = None
        self.ws = None
        self.subscriptions = {}
        self.price_callbacks = []
        self.running = False
        
        # Live data storage
        self.live_prices = {}
        self.live_orderbooks = {}
        self.live_trades = []

    async def start(self):
        """Start the feed with websocket connection"""
        logger.info("Starting Kraken feed...")
        self.running = True
        self.session = aiohttp.ClientSession()
        logger.info("Created HTTP session")
        await self._start_websocket()
        logger.info("WebSocket initialized")

    async def close(self):
        """Cleanup connections"""
        logger.info("Closing Kraken feed connections...")
        self.running = False
        if self.ws:
            await self.ws.close()
            logger.info("WebSocket closed")
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("HTTP session closed")

    async def _start_websocket(self):
        """Initialize websocket connection"""
        try:
            logger.info("Attempting WebSocket connection...")
            
            # First get active pairs synchronously
            pairs = await self.get_active_pairs()
            if not pairs:
                logger.error("Failed to get active pairs")
                return
            
            logger.info(f"Retrieved {len(pairs)} active pairs")
            
            ws_conn = await self.session.ws_connect(self.ws_url, timeout=30)
            logger.info("WebSocket connected successfully")
            
            # Set the websocket
            self.ws = ws_conn
            
            # Subscribe to ticker updates
            subscribe_message = {
                "event": "subscribe",
                "pair": pairs,
                "subscription": {
                    "name": "ticker"
                }
            }
            
            logger.info("Sending subscription message...")
            await ws_conn.send_json(subscribe_message)
            logger.info("Subscription message sent")
            
            # Start message handling loop
            asyncio.create_task(self._handle_websocket_messages(ws_conn))
            logger.info("WebSocket message handler started")
                            
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            if self.running:
                logger.info("Attempting reconnection in 5 seconds...")
                await asyncio.sleep(5)
                await self._start_websocket()
            
    async def _handle_websocket_messages(self, ws_conn):
        """Handle incoming websocket messages"""
        logger.info("Starting WebSocket message handler")
        try:
            async for msg in ws_conn:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        
                        # Log periodic heartbeats but not every message
                        if time.time() % 60 < 1:  # Log once per minute
                            logger.info("WebSocket connection alive")
                        
                        # Handle ticker updates
                        if isinstance(data, list) and len(data) > 2:
                            pair = data[3]
                            ticker = data[1]
                            
                            price = float(ticker['c'][0])  # Last trade closed price
                            volume = float(ticker['v'][1])  # 24h volume
                            high = float(ticker['h'][1])    # 24h high
                            low = float(ticker['l'][1])     # 24h low
                            
                            # Update live price data
                            self.live_prices[pair] = {
                                'price': price,
                                'volume': volume,
                                'high': high,
                                'low': low,
                                'timestamp': datetime.now(timezone.utc)
                            }
                            
                            # Notify callbacks
                            for callback in self.price_callbacks:
                                await callback(pair, price)
                                
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in message: {msg.data[:100]}...")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {msg.data}")
                    break
                    
        except Exception as e:
            logger.error(f"WebSocket message handler error: {e}")
        finally:
            logger.info("WebSocket message handler stopped")
            if self.running:
                logger.info("Restarting WebSocket connection...")
                await asyncio.sleep(5)
                await self._start_websocket()

    def add_price_callback(self, callback: Callable):
        """Add callback for price updates"""
        self.price_callbacks.append(callback)
        logger.info("Added new price callback")

    async def get_active_pairs(self) -> List[str]:
        """Get most active trading pairs"""
        try:
            logger.info("Fetching active pairs...")
            async with self.session.get(f"{self.api_url}/0/public/AssetPairs") as response:
                if response.status == 200:
                    data = await response.json()
                    if 'result' not in data:
                        logger.error(f"Invalid API response: {data}")
                        return []
                    pairs = [pair for pair in data['result'].keys() 
                            if '.d' not in pair]  # Filter out dark pool pairs
                    logger.info(f"Retrieved {len(pairs)} pairs")
                    return pairs[:20]  # Return top 20 pairs
                logger.error(f"Failed to fetch pairs: {response.status}")
                return []
        except Exception as e:
            logger.error(f"Error getting active pairs: {e}")
            return []

    async def get_ticker(self, pair: str) -> Optional[Dict]:
        """Get current ticker data, preferring live data if available"""
        try:
            # Use live data if available
            if pair in self.live_prices:
                live_data = self.live_prices[pair]
                return {
                    'price': live_data['price'],
                    'volume24h': live_data['volume'],
                    'change24h': ((live_data['price'] - live_data['low']) / 
                                live_data['low'] * 100 if live_data['low'] > 0 else 0)
                }
            
            # Fallback to REST API
            logger.info(f"Fetching ticker data for {pair}")
            result = await self._api_request('public/Ticker', {'pair': pair})
            if result and pair in result:
                ticker_data = result[pair]
                return {
                    'price': float(ticker_data['c'][0]),
                    'volume24h': float(ticker_data['v'][1]),
                    'change24h': (float(ticker_data['c'][0]) - float(ticker_data['o'])) / 
                                float(ticker_data['o']) * 100
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting ticker for {pair}: {str(e)}")
            return None

    async def _api_request(self, endpoint: str, data: dict = None) -> dict:
        """Make a request to Kraken API"""
        if data is None:
            data = {}
        url = f"{self.api_url}/0/{endpoint}"
        
        try:
            async with self.session.get(url, params=data) as response:
                if response.status != 200:
                    logger.error(f"API request failed: {response.status}")
                    return {}
                    
                result = await response.json()
                if result.get('error'):
                    logger.error(f"API error: {result['error']}")
                    return {}
                    
                return result.get('result', {})
                
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            return {}