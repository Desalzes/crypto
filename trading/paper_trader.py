import json
import os
import logging
from typing import Dict
from datetime import datetime
import pandas as pd

class PaperTrader:
    def __init__(self, initial_balance: float = 1000.0):
        self.initial_balance = initial_balance
        self.positions = {}
        self.trades = []
        self.balance = self.load_state()
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
    def _setup_logging(self):
        log_dir = "logs/trades"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        self.trade_log = os.path.join(log_dir, f"trades_{datetime.now().strftime('%Y%m%d')}.csv")
        if not os.path.exists(self.trade_log):
            pd.DataFrame(columns=['timestamp', 'symbol', 'action', 'quantity', 'price', 'balance']).to_csv(self.trade_log, index=False)

    def load_state(self) -> float:
        try:
            if os.path.exists('trading_state.json'):
                with open('trading_state.json', 'r') as f:
                    state = json.load(f)
                    return state.get('balance', self.initial_balance)
            return self.initial_balance
        except Exception as e:
            return self.initial_balance
            
    def save_state(self):
        try:
            current_time = datetime.now().isoformat()
            with open('trading_state.json', 'w') as f:
                json.dump({
                    'balance': self.balance,
                    'last_updated': current_time,
                    'positions': self.positions
                }, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving state: {e}")

    def log_trade(self, symbol: str, action: str, quantity: float, price: float):
        trade_data = pd.DataFrame([{
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'action': action,
            'quantity': quantity,
            'price': price,
            'balance': self.balance
        }])
        trade_data.to_csv(self.trade_log, mode='a', header=False, index=False)
            
    def get_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        portfolio_value = self.balance
        for symbol, position in self.positions.items():
            if position['quantity'] > 0:
                current_price = current_prices.get(symbol, position['avg_price'])
                portfolio_value += position['quantity'] * current_price
        return portfolio_value
        
    def get_position(self, symbol: str) -> Dict:
        return self.positions.get(symbol, {'quantity': 0, 'avg_price': 0})
        
    def place_order(self, symbol: str, action: str, quantity: float, price: float) -> bool:
        try:
            if action == 'BUY':
                success = self._place_buy(symbol, quantity, price)
            elif action == 'SELL':
                success = self._place_sell(symbol, quantity, price)
            else:
                return False
                
            if success:
                self.log_trade(symbol, action, quantity, price)
                self.save_state()
            return success
            
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            return False
            
    def _place_buy(self, symbol: str, quantity: float, price: float) -> bool:
        cost = quantity * price
        if cost > self.balance:
            return False
            
        if symbol not in self.positions:
            self.positions[symbol] = {'quantity': 0, 'avg_price': 0}
            
        position = self.positions[symbol]
        total_cost = (position['quantity'] * position['avg_price']) + cost
        total_quantity = position['quantity'] + quantity
        
        position['avg_price'] = total_cost / total_quantity if total_quantity > 0 else 0
        position['quantity'] = total_quantity
        
        self.balance -= cost
        return True
        
    def _place_sell(self, symbol: str, quantity: float, price: float) -> bool:
        if symbol not in self.positions:
            return False
            
        position = self.positions[symbol]
        if position['quantity'] < quantity:
            return False
            
        revenue = quantity * price
        
        position['quantity'] -= quantity
        
        if position['quantity'] == 0:
            position['avg_price'] = 0
            
        self.balance += revenue
        return True