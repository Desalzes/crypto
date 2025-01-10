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
        self.analyzed_prices = {}
        self.last_analysis_time = {}
        self.analysis_interval = 60  # Minimum seconds between analyses for each pair
        self.pairs = set()
        self.trade_threshold = 0.45
        
    async def start(self):
        """Start the trading manager"""
        try:
            logger.info("Initializing trading manager...")
            
            # Initialize feed with websocket connection
            logger.info("Starting Kraken feed...")
            await self.feed.start()
            logger.info("Kraken feed started successfully")
            
            # Set up price update callback
            self.feed.add_price_callback(self.price_update_callback)
            logger.info("Price callback registered")
            
            # Get initial active pairs
            logger.info("Fetching initial active pairs...")
            initial_pairs = await self.feed.get_active_pairs()
            self.pairs = set(initial_pairs[:14])  # Top 14 pairs
            logger.info(f"Tracking pairs: {', '.join(self.pairs)}")
            
            print(f"\nStarting trading bot with ${self.trader.get_portfolio_value({}):.2f}")
            logger.info("Starting crypto trading...")
            
            self.running = True
            
            # Keep the main loop running and handle portfolio updates
            while self.running:
                try:
                    current_balance = self.trader.get_portfolio_value({})
                    if current_balance != self.last_balance:
                        print(f"\nPortfolio Value: ${current_balance:.2f}")
                        await self.update_trading_state(current_balance)
                    
                    # Update active pairs list every hour
                    if time.time() % 3600 < 1:
                        new_pairs = await self.feed.get_active_pairs()
                        old_pairs = self.pairs
                        self.pairs = set(new_pairs[:14])
                        if old_pairs != self.pairs:
                            logger.info(f"Updated tracking pairs: {', '.join(self.pairs)}")
                    
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    if self.running:
                        await asyncio.sleep(5)
                
        except KeyboardInterrupt:
            logger.info("Trading loop interrupted by user")
        except Exception as e:
            logger.error(f"Critical error in trading loop: {e}")
        finally:
            await self.cleanup()

    async def price_update_callback(self, pair: str, price: float):
        """Handle real-time price updates"""
        current_time = time.time()
        last_time = self.last_analysis_time.get(pair, 0)
        
        # Only analyze if enough time has passed since last analysis
        if current_time - last_time >= self.analysis_interval:
            try:
                if pair in self.pairs:  # Only analyze tracked pairs
                    logger.debug(f"Analyzing price update for {pair}: ${price:.4f}")
                    
                    # Get fresh OHLCV data
                    ohlcv_data = await self.feed.get_all_timeframe_data(pair)
                    
                    # Get current ticker data
                    ticker = await self.feed.get_ticker(pair)
                    
                    if ticker and ohlcv_data:
                        # Perform analysis
                        analysis = await self.market_analyzer.analyze_market(pair, ohlcv_data)
                        
                        # Print analysis results
                        print(f"\n{pair} Update:")
                        print(f"  Price: ${price:.4f}")
                        print(f"  24h Change: {ticker.get('change24h', 0):+.2f}%")
                        print(f"  Market Regime: {analysis['market_context']['regime']}")
                        print(f"  Action: {analysis['summary']['primary_action']}")
                        print(f"  Confidence: {analysis['summary']['confidence']:.2f}")
                        print(f"  Risk Level: {analysis['summary']['risk_level']}")
                        
                        # Execute trades if signals are strong enough
                        if analysis['summary']['primary_action'] != 'HOLD' and \
                           analysis['summary']['confidence'] >= self.trade_threshold:
                            
                            position_size = self.strategy.calculate_position_size(
                                self.trader.get_portfolio_value({}),
                                analysis['summary']['confidence'],
                                price
                            )
                            
                            # Adjust position size based on market context
                            position_size *= analysis['trading_parameters'].get('position_size', 1.0)
                            
                            if position_size > 0:
                                success = self.trader.place_order(
                                    pair,
                                    analysis['summary']['primary_action'],
                                    position_size,
                                    price
                                )
                                
                                if success:
                                    print(f"  >> EXECUTED: {analysis['summary']['primary_action']} {position_size:.8f} {pair}")
                                    if 'stop_loss' in analysis['trading_parameters']:
                                        print(f"     Stop Loss: ${analysis['trading_parameters']['stop_loss']:.4f}")
                                    if 'take_profit' in analysis['trading_parameters']:
                                        print(f"     Take Profit: ${analysis['trading_parameters']['take_profit']:.4f}")
                        
                        # Update position info
                        position = self.trader.get_position(pair)
                        if position['quantity'] > 0:
                            profit_pct = ((price - position['avg_price']) / position['avg_price'] * 100)
                            print(f"  Current Position:")
                            print(f"    Size: {position['quantity']:.8f}")
                            print(f"    Entry Price: ${position['avg_price']:.4f}")
                            print(f"    P/L: {profit_pct:+.2f}%")
                        
                        # Store analysis time
                        self.last_analysis_time[pair] = current_time
                        
            except Exception as e:
                logger.error(f"Error processing price update for {pair}: {e}")

    async def cleanup(self):
        """Cleanup all connections and resources"""
        logger.info("Cleaning up trading manager...")
        self.running = False
        await self.feed.close()
        
        # Save final state
        current_balance = self.trader.get_portfolio_value({})
        await self.update_trading_state(current_balance)
        logger.info("Cleanup complete")

    async def update_trading_state(self, balance: float):
        """Update trading state and save to file"""
        try:
            if balance != self.last_balance:
                state_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'trading_state.json')
                
                # Load current state
                if os.path.exists(state_file):
                    with open(state_file, 'r') as f:
                        state = json.load(f)
                else:
                    state = {
                        "balance": balance,
                        "history": [],
                        "positions": {}
                    }
                
                # Update state
                state["balance"] = balance
                state["history"].append({
                    "balance": balance,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Save updated state
                with open(state_file, 'w') as f:
                    json.dump(state, f, indent=2)
                
                self.last_balance = balance
                logger.info(f"Updated trading state - New Balance: ${balance:.2f}")
                
        except Exception as e:
            logger.error(f"Error updating trading state: {e}")

    async def run_llm_review(self):
        """Perform LLM review of indicators and market conditions"""
        print("\nInitiating LLM Review of Indicators...")
        try:
            pairs = list(self.pairs) if self.pairs else await self.feed.get_active_pairs()
            pairs = pairs[:14]  # Top 14 pairs
            
            print("\nAnalyzing Market Data:")
            print("-" * 50)
            
            for pair in pairs:
                try:
                    ticker = await self.feed.get_ticker(pair)
                    if not ticker:
                        continue
                        
                    ohlcv = await self.feed.get_all_timeframe_data(pair)
                    if not ohlcv:
                        continue
                        
                    analysis = await self.market_analyzer.analyze_market(pair, ohlcv)
                    
                    print(f"\n{pair}:")
                    print(f"  Price: ${float(ticker['price']):.4f}")
                    print(f"  Market Regime: {analysis['market_context']['regime']}")
                    print(f"  Volatility: {analysis['market_context']['volatility']}")
                    print(f"  Risk Level: {analysis['summary']['risk_level']}")
                    
                    for indicator, details in analysis.get('technical_indicators', {}).items():
                        print(f"  {indicator}:")
                        print(f"    Signal: {details.get('signal', 'N/A')}")
                        print(f"    Reliability: {details.get('reliability', 0):.2f}")
                        if details.get('warnings'):
                            print(f"    Warnings: {', '.join(details['warnings'])}")
                    
                    await asyncio.sleep(1)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Error analyzing {pair}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in LLM review: {e}")
            print(f"Error during LLM review: {e}")
        finally:
            print("\nLLM Review completed.")
            input("Press Enter to continue...")