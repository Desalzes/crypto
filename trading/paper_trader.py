import json
import os
from typing import Dict
import logging

class PaperTrader:
    def __init__(self, initial_balance=1000):
        self.state_file = "trading_state.json"
        self.load_state(initial_balance)
        
    def load_state(self, initial_balance):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.balance = float(state['balance'])
                    self.positions = state['positions']
                logging.info(f"\n-----------------\nBalance: ${self.balance:.2f}\n-----------------\n")
            else:
                self.balance = float(initial_balance)
                self.positions = {}
                self.save_state()
        except Exception as e:
            logging.error(f"Error loading state: {e}")
            self.balance = float(initial_balance)
            self.positions = {}

    def save_state(self):
        try:
            state = {
                'balance': float(self.balance),
                'positions': self.positions
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            logging.error(f"Error saving state: {e}")

    def get_portfolio_value(self, prices: Dict[str, float]) -> float:
        """Calculate total portfolio value including all positions"""
        value = self.balance
        for symbol, position in self.positions.items():
            if symbol in prices:
                value += position['quantity'] * prices[symbol]
        return value

    def get_position(self, symbol: str) -> Dict:
        """Get current position for a symbol"""
        return self.positions.get(symbol, {'quantity': 0, 'avg_price': 0})

    def place_order(self, symbol: str, action: str, quantity: float, price: float) -> bool:
        """Execute a trade order"""
        cost = quantity * price
        
        if action == 'BUY':
            if cost > self.balance:
                return False
            if symbol not in self.positions:
                self.positions[symbol] = {'quantity': 0, 'avg_price': 0}
            position = self.positions[symbol]
            total_cost = (position['quantity'] * position['avg_price']) + cost
            total_quantity = position['quantity'] + quantity
            position['avg_price'] = total_cost / total_quantity
            position['quantity'] = total_quantity
            self.balance -= cost
            
        elif action == 'SELL':
            if symbol not in self.positions or self.positions[symbol]['quantity'] < quantity:
                return False
            self.positions[symbol]['quantity'] -= quantity
            if self.positions[symbol]['quantity'] == 0:
                del self.positions[symbol]
            self.balance += cost
        
        self.save_state()
        logging.info(f"\n-----------------\nBalance: ${self.balance:.2f}\n-----------------\n")
        return True