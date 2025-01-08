import pandas as pd
from typing import Dict
from datetime import datetime
import json
import os
import logging

class PerformanceTracker:
    def __init__(self):
        self.trades = []
        self.daily_stats = {}
        self.trades_file = "trade_history.json"
        self.load_history()
        
    def load_history(self):
        try:
            if os.path.exists(self.trades_file):
                with open(self.trades_file, 'r') as f:
                    data = json.load(f)
                    self.trades = data.get('trades', [])
                    self.daily_stats = data.get('daily_stats', {})
        except Exception as e:
            logging.error(f"Error loading trade history: {e}")
            
    def save_history(self):
        try:
            with open(self.trades_file, 'w') as f:
                json.dump({
                    'trades': self.trades,
                    'daily_stats': self.daily_stats
                }, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving trade history: {e}")
        
    def add_trade(self, trade: Dict):
        trade_with_time = {
            **trade,
            'timestamp': datetime.now().isoformat(),
            'profit_loss': 0  # Will be updated when position is closed
        }
        self.trades.append(trade_with_time)
        self._update_stats(trade_with_time)
        self.save_history()
        
    def _update_stats(self, trade: Dict):
        date = trade['timestamp'].split('T')[0]
        if date not in self.daily_stats:
            self.daily_stats[date] = {
                'trades': 0,
                'wins': 0,
                'profit': 0,
                'indicators': {}
            }
            
        stats = self.daily_stats[date]
        stats['trades'] += 1
        
        if trade['profit_loss'] > 0:
            stats['wins'] += 1
        stats['profit'] += trade['profit_loss']
        
        for indicator in trade['indicators']:
            if indicator not in stats['indicators']:
                stats['indicators'][indicator] = {'success': 0, 'total': 0}
            stats['indicators'][indicator]['total'] += 1
            if trade['profit_loss'] > 0:
                stats['indicators'][indicator]['success'] += 1
                
    def get_summary(self) -> Dict:
        """Get performance summary"""
        if not self.trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'total_profit': 0,
                'best_indicators': []
            }
            
        winning_trades = len([t for t in self.trades if t['profit_loss'] > 0])
        total_trades = len(self.trades)
        
        return {
            'total_trades': total_trades,
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
            'total_profit': sum(t['profit_loss'] for t in self.trades),
            'best_indicators': self._get_best_indicators()
        }
        
    def _get_best_indicators(self) -> list:
        """Get best performing indicators"""
        indicator_stats = {}
        
        for date_stats in self.daily_stats.values():
            for indicator, stats in date_stats['indicators'].items():
                if indicator not in indicator_stats:
                    indicator_stats[indicator] = {'success': 0, 'total': 0}
                indicator_stats[indicator]['success'] += stats['success']
                indicator_stats[indicator]['total'] += stats['total']
                
        # Calculate win rates
        win_rates = []
        for indicator, stats in indicator_stats.items():
            if stats['total'] > 0:
                win_rate = stats['success'] / stats['total']
                win_rates.append((indicator, win_rate))
                
        # Return top 5 indicators
        return sorted(win_rates, key=lambda x: x[1], reverse=True)[:5]