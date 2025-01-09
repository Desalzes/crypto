import asyncio
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from trading.trading_manager import TradingManager
import logging

def print_menu():
    print("\nCrypto Trading Options:")
    print("1. Live Trading")
    print("2. Train ML Model")
    print("3. LLM Review of Indicators")
    print("4. Reset Balance")
    print("5. Update Database")
    print("6. Exit")
    return input("\nSelect option (1-6): ")

async def handle_menu(config):
    manager = None
    while True:
        choice = print_menu()
        
        try:
            if choice == "1":
                if not manager:
                    manager = TradingManager(config, "crypto")
                try:
                    await manager.run_trading_loop()
                except KeyboardInterrupt:
                    print("\nShutting down trading...")
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
                    
            elif choice == "6":
                print("Exiting program...")
                break
            else:
                print("Invalid option. Please try again.")

        except Exception as e:
            print(f"Error handling menu choice: {e}")

async def main():
    load_dotenv()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'config', 'indicators_config.json')
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    await handle_menu(config)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise