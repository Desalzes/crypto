import numpy as np
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class PositionManager:
    def __init__(self, initial_balance: float = 1000.0):
        self.initial_balance = initial_balance
        self.positions = {}
        self.trade_history = []
        
    def calculate_kelly_position_size(self, win_rate: float, profit_factor: float, risk_factor: float = 0.25) -> float:
        """
        Calculate position size using the Kelly Criterion
        
        Args:
            win_rate: Historical win rate (0-1)
            profit_factor: Ratio of average win to average loss
            risk_factor: Fraction of Kelly to use (default 0.25 for safety)
            
        Returns:
            Suggested position size as a fraction of portfolio
        """
        kelly_percentage = win_rate - ((1 - win_rate) / profit_factor)
        # Apply fractional Kelly and ensure non-negative
        safe_size = max(0, kelly_percentage * risk_factor)
        # Cap at 20% of portfolio for safety
        return min(safe_size, 0.2)

    def calculate_dynamic_stop_loss(self, atr: float, price: float, multiplier: float = 2.0) -> float:
        """Calculate dynamic stop loss using ATR"""
        return atr * multiplier

    def calculate_trailing_stop(self, current_price: float, position: Dict, atr: float) -> float:
        """
        Calculate trailing stop loss that moves up with profitable trades
        
        Args:
            current_price: Current market price
            position: Position dictionary containing entry price and other details
            atr: Current ATR value
        """
        if not position or 'entry_price' not in position:
            return 0
            
        entry_price = position['entry_price']
        initial_stop = self.calculate_dynamic_stop_loss(atr, entry_price)
        
        # If we're in profit, calculate trailing stop
        if current_price > entry_price:
            profit_distance = current_price - entry_price
            trailing_stop = current_price - initial_stop
            
            # If we're up more than 2x ATR, move stop loss to breakeven
            if profit_distance > (2 * atr):
                trailing_stop = max(trailing_stop, entry_price)
                
            # If we're up more than 3x ATR, trail by ATR
            if profit_distance > (3 * atr):
                trailing_stop = current_price - atr
                
            return trailing_stop
        
        return entry_price - initial_stop

    def update_position_stops(self, symbol: str, current_price: float, atr: float):
        """Update trailing stops for a position"""
        if symbol in self.positions:
            new_stop = self.calculate_trailing_stop(
                current_price, 
                self.positions[symbol],
                atr
            )
            self.positions[symbol]['stop_loss'] = new_stop
            
    def calculate_volatility_adjusted_size(self, atr: float, price: float, risk_per_trade: float = 0.02) -> float:
        """
        Calculate position size based on volatility
        
        Args:
            atr: Current ATR value
            price: Current market price
            risk_per_trade: Maximum risk per trade as fraction of portfolio
        """
        volatility_factor = atr / price  # Normalized volatility
        # Reduce position size when volatility is high
        return risk_per_trade * (1 / volatility_factor)
        
    def get_optimal_position_size(self, 
                                balance: float,
                                win_rate: float,
                                profit_factor: float,
                                atr: float,
                                price: float) -> float:
        """
        Combine Kelly Criterion and volatility adjustment for final position size
        """
        kelly_size = self.calculate_kelly_position_size(win_rate, profit_factor)
        vol_size = self.calculate_volatility_adjusted_size(atr, price)
        
        # Take the more conservative of the two
        position_size = min(kelly_size, vol_size)
        
        # Calculate actual units based on account balance
        return position_size * balance / price