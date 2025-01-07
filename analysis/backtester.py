import pandas as pd
import numpy as np
from typing import Dict
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis.indicators import Indicators
import asyncio
import logging
import torch

class Backtester:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.logger = logging.getLogger(__name__)
        
    def _prepare_batch_data(self, df: pd.DataFrame, window_size: int):
        # Convert to tensors with batch processing
        closes = torch.tensor(df['close'].values, device=self.device, dtype=torch.float32)
        opens = torch.tensor(df['open'].values, device=self.device, dtype=torch.float32)
        highs = torch.tensor(df['high'].values, device=self.device, dtype=torch.float32)
        lows = torch.tensor(df['low'].values, device=self.device, dtype=torch.float32)
        return closes, opens, highs, lows

    async def run_backtest(self, symbol: str, data: Dict[str, pd.DataFrame]):
        try:
            results = {}
            for timeframe, df in data.items():
                if len(df) < 500:
                    continue
                    
                signals = await self._test_timeframe(timeframe, df)
                results[timeframe] = signals
                
            return self._combine_results(results)
            
        except Exception as e:
            self.logger.error(f"Backtest error for {symbol}: {e}")
            return {'win_rate': 0, 'avg_profit': 0, 'total_trades': 0}

    async def _test_timeframe(self, timeframe: str, df: pd.DataFrame):
        window_size = 500
        signals = []
        equity = 1000
        position = 0
        entry_price = 0
        
        # Batch process data
        closes, opens, highs, lows = self._prepare_batch_data(df, window_size)
        
        # Create signal masks using vectorized operations
        rsi_buy_mask = torch.tensor([indicators['rsi'] < 30 for indicators in 
                                   [Indicators.calculate_all(df.iloc[i-window_size:i], timeframe) 
                                    for i in range(window_size, len(df))]], device=self.device)
        
        macd_buy_mask = torch.tensor([indicators['macd'] > indicators['macd_signal'] for indicators in 
                                    [Indicators.calculate_all(df.iloc[i-window_size:i], timeframe) 
                                     for i in range(window_size, len(df))]], device=self.device)
        
        buy_signals = torch.logical_and(rsi_buy_mask, macd_buy_mask)
        
        # Process signals in batches
        for i in range(window_size, len(df)):
            if buy_signals[i-window_size]:
                if position == 0:
                    position = equity / closes[i].item()
                    entry_price = closes[i].item()
                elif position > 0:
                    equity = position * closes[i].item()
                    signals.append({
                        'type': 'SELL',
                        'profit': (closes[i].item() - entry_price) / entry_price
                    })
                    position = 0
                    
        win_rate = len([s for s in signals if s['profit'] > 0]) / len(signals) if signals else 0
        avg_profit = sum(s['profit'] for s in signals) / len(signals) if signals else 0
        
        return {
            'signals': signals,
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'total_trades': len(signals)
        }

    def _combine_results(self, results):
        if not results:
            return {'win_rate': 0, 'avg_profit': 0, 'total_trades': 0}
            
        total_trades = sum(r['total_trades'] for r in results.values())
        if total_trades == 0:
            return {'win_rate': 0, 'avg_profit': 0, 'total_trades': 0}
            
        weighted_win_rate = sum(r['win_rate'] * r['total_trades'] for r in results.values()) / total_trades
        weighted_profit = sum(r['avg_profit'] * r['total_trades'] for r in results.values()) / total_trades
            
        return {
            'win_rate': weighted_win_rate,
            'avg_profit': weighted_profit,
            'total_trades': total_trades
        }