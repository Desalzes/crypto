import asyncio
import json
import os
from dotenv import load_dotenv
from market_data.kraken_feed import KrakenFeed
from trading.paper_trader import PaperTrader
from trading.crypto_strategy import CryptoStrategy
from database.db_manager import DatabaseManager
from analysis.model_trainer import ModelTrainer
from utils.error_handler import setup_logging
from trading_manager import TradingManager
import logging

def print_menu():
    print("\nCrypto Trading Options:")
    print("1. Live Trading")
    print("2. Train ML Model")
    print("3. LLM Review of Indicators")
    print("4. Exit")
    return input("\nSelect option (1-4): ")

async def handle_menu(config, db):
    while True:
        choice = print_menu()
        
        try:
            if choice == "1":
                manager = TradingManager(config, db, "crypto")
                try:
                    logging.info("Starting crypto trading...")
                    await manager.run_trading_loop()
                except KeyboardInterrupt:
                    logging.info("Shutting down crypto trading...")
                finally:
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
                manager = TradingManager(config, db, "crypto")
                try:
                    await manager.run_llm_review()
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logging.error(f"Error in LLM review: {e}")
                finally:
                    await manager.cleanup()
                    
            elif choice == "4":
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