import asyncio
import json
import os
import glob
from datetime import datetime
from dotenv import load_dotenv
from market_data.kraken_feed import KrakenFeed
from trading.paper_trader import PaperTrader
from trading.crypto_strategy import CryptoStrategy
from database import DatabaseManager
from core.model_trainer import ModelTrainer
from utils.error_handler import setup_logging
from tqdm import tqdm
import logging
import pandas as pd

def print_menu():
    print("\nCrypto Trading Options:")
    print("1. Live Trading")
    print("2. Train ML Model")
    print("3. LLM Review of Indicators")
    print("4. Reset Balance")
    print("5. Update Database")
    print("6. Exit")
    return input("\nSelect option (1-6): ")

class TradingManager:
    def __init__(self, config, db, mode="crypto"):
        self.config = config
        self.db = db
        self.mode = mode
        self.feed = KrakenFeed()
        self.trader = PaperTrader()
        self.strategy = CryptoStrategy(db)
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
        if self.feed:
            await self.feed.close()

    async def analyze_pairs(self, pairs):
        with tqdm(total=len(pairs), desc="Analyzing markets") as pbar:
            results = []
            for i in range(0, len(pairs), self.batch_size):
                batch = pairs[i:i+self.batch_size]
                for pair in batch:
                    ticker = await self.feed.get_ticker(pair)
                    if ticker:
                        results.append((pair, ticker))
                    pbar.update(1)
                if i + self.batch_size < len(pairs):
                    await asyncio.sleep(0.1)
            return results

    async def run_trading_loop(self):
        self.running = True
        print(f"\nStarting trading bot with ${self.trader.get_portfolio_value({}):.2f}")
        
        try:
            while self.running:
                try:
                    pairs = await self.feed.get_active_pairs()
                    pairs = pairs[:14]
                    results = await self.analyze_pairs(pairs)
                    
                    current_value = self.trader.get_portfolio_value({})
                    print(f"\nPortfolio Value: ${current_value:.2f}")
                    
                    if self.running:
                        print(f"\nWaiting {self.loop_interval} seconds...")
                        await asyncio.sleep(self.loop_interval)

                except Exception as e:
                    logging.error(f"Error in trading iteration: {e}")
                    if self.running:
                        await asyncio.sleep(self.loop_interval)
                        
        except KeyboardInterrupt:
            logging.info("Trading loop interrupted by user")
        finally:
            await self.cleanup()

async def update_database():
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'historical')
    if not os.path.exists(data_dir):
        print("No data directory found")
        return

    csv_files = glob.glob(os.path.join(data_dir, '*.csv'))
    for file in csv_files:
        try:
            print(f"Processing {os.path.basename(file)}...")
            df = pd.read_csv(file)
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.sort_values('timestamp')
                df.to_csv(file, index=False)
                print(f"Updated {os.path.basename(file)}")
        except Exception as e:
            print(f"Error processing {os.path.basename(file)}: {e}")

async def handle_menu(config, db):
    manager = None
    while True:
        choice = print_menu()
        
        try:
            if choice == "1":
                if not manager:
                    manager = TradingManager(config, db)
                try:
                    logging.info("Starting crypto trading...")
                    await manager.run_trading_loop()
                except KeyboardInterrupt:
                    logging.info("Shutting down crypto trading...")
                finally:
                    if manager:
                        await manager.cleanup()
                    
            elif choice == "2":
                trainer = ModelTrainer()
                try:
                    logging.info("Starting crypto model training...")
                    data = await trainer.download_training_data()
                    if data:
                        logging.info("Preparing features for training...")
                        features, labels = trainer.prepare_features(data)
                        if len(features) > 0:
                            logging.info("Starting model training...")
                            model_path, feature_path = trainer.train_model(features, labels)
                            logging.info(f"Model saved to {model_path}")
                            logging.info(f"Feature names saved to {feature_path}")
                        else:
                            logging.error("No valid features generated for training")
                    else:
                        logging.error("No data downloaded for training")
                except Exception as e:
                    logging.error(f"Error in model training: {e}")
                    
            elif choice == "3":
                if not manager:
                    manager = TradingManager(config, db)
                try:
                    await manager.run_trading_loop()
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logging.error(f"Error in review: {e}")
                finally:
                    if manager:
                        await manager.cleanup()

            elif choice == "4":
                state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading_state.json')
                reset_state = {
                    "balance": 1000.00,
                    "history": [{
                        "balance": 1000.00,
                        "timestamp": datetime.now().isoformat()
                    }]
                }
                with open(state_file, 'w') as f:
                    json.dump(reset_state, f, indent=2)
                print("Balance reset to $1000.00")
                if manager:
                    await manager.cleanup()
                    manager = None

            elif choice == "5":
                print("Updating database files...")
                await update_database()
                print("Database update complete")
                    
            elif choice == "6":
                logging.info("Exiting program...")
                break
            else:
                print("Invalid option. Please try again.")

        except Exception as e:
            logging.error(f"Error handling menu choice: {e}")

async def main():
    setup_logging()
    load_dotenv()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'config', 'indicators_config.json')
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    db = DatabaseManager()
    await handle_menu(config, db)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise