import asyncio
import json
import os
import glob
from datetime import datetime
from dotenv import load_dotenv
from market_data.kraken_feed import KrakenFeed
from trading.paper_trader import PaperTrader
from trading.crypto_strategy import CryptoStrategy
from database.db_manager import DatabaseManager
from core.model_trainer import ModelTrainer
from utils.error_handler import setup_logging
from trading.trading_manager import TradingManager
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
                    manager = TradingManager(config, db, "crypto")
                try:
                    logging.info("Starting crypto trading...")
                    await manager.start()  # Using new WebSocket-based start method
                except KeyboardInterrupt:
                    logging.info("Shutting down crypto trading...")
                finally:
                    if manager:
                        await manager.cleanup()
                        manager = None
                    
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
                    print(f"\nError during model training: {e}")
                    
            elif choice == "3":
                print("\nInitiating LLM Review of Indicators...")
                if not manager:
                    manager = TradingManager(config, db, "crypto")
                try:
                    await manager.run_llm_review()
                except Exception as e:
                    logging.error(f"Error in LLM review: {e}")
                    print(f"\nError during LLM review: {e}")
                finally:
                    if manager:
                        await manager.cleanup()
                        manager = None

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
                print("\nBalance reset to $1000.00")
                if manager:
                    await manager.cleanup()
                    manager = None
                input("\nPress Enter to continue...")

            elif choice == "5":
                print("\nUpdating database files...")
                await update_database()
                print("\nDatabase update complete")
                input("\nPress Enter to continue...")
                    
            elif choice == "6":
                logging.info("Exiting program...")
                if manager:
                    await manager.cleanup()
                break
            else:
                print("\nInvalid option. Please try again.")
                input("\nPress Enter to continue...")

        except Exception as e:
            logging.error(f"Error handling menu choice: {e}")
            print(f"\nError: {e}")
            input("\nPress Enter to continue...")
            if manager:
                await manager.cleanup()
                manager = None

async def main():
    setup_logging()
    load_dotenv()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'config', 'indicators_config.json')
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        logging.error(f"Error loading config: {e}")
        print(f"Error loading configuration: {e}")
        return
    
    db = DatabaseManager()
    await handle_menu(config, db)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        print(f"\nUnexpected error: {e}")
        raise