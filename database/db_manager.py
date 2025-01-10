import sqlite3
import json
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime

class DatabaseManager:
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = os.path.join(self.script_dir, 'trading.db')
        self._init_db()

    def _init_db(self):
        """Initialize the database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create tables if they don't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS indicators (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pair TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        indicator TEXT NOT NULL,
                        success_rate REAL,
                        total_trades INTEGER,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pair TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        action TEXT NOT NULL,
                        price REAL NOT NULL,
                        quantity REAL NOT NULL,
                        profit_loss REAL,
                        indicators TEXT
                    )
                ''')
                
                conn.commit()
                
        except Exception as e:
            logging.error(f"Error initializing database: {e}")

    def update_indicator_performance(self, pair: str, timeframe: str, 
                                   indicator: str, success_rate: float,
                                   total_trades: int):
        """Update indicator performance metrics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO indicators 
                    (pair, timeframe, indicator, success_rate, total_trades, last_updated)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (pair, timeframe, indicator, success_rate, total_trades))
                
                conn.commit()
                
        except Exception as e:
            logging.error(f"Error updating indicator performance: {e}")

    def get_best_indicators(self, pair: str, timeframe: str) -> List[Dict]:
        """Get best performing indicators for a pair and timeframe"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT indicator, success_rate, total_trades
                    FROM indicators
                    WHERE pair = ? AND timeframe = ?
                    AND total_trades >= 10
                    ORDER BY success_rate DESC
                    LIMIT 5
                ''', (pair, timeframe))
                
                results = cursor.fetchall()
                return [
                    {
                        'indicator': row[0],
                        'success_rate': row[1],
                        'total_trades': row[2]
                    }
                    for row in results
                ]
                
        except Exception as e:
            logging.error(f"Error getting best indicators: {e}")
            return []

    def add_trade(self, trade_data: Dict):
        """Record a new trade"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO trades 
                    (pair, action, price, quantity, profit_loss, indicators)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    trade_data['pair'],
                    trade_data['action'],
                    trade_data['price'],
                    trade_data['quantity'],
                    trade_data.get('profit_loss', 0),
                    json.dumps(trade_data.get('indicators', {}))
                ))
                
                conn.commit()
                
        except Exception as e:
            logging.error(f"Error adding trade: {e}")

    def get_trade_history(self, pair: Optional[str] = None) -> List[Dict]:
        """Get trading history with optional pair filter"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT pair, timestamp, action, price, quantity, profit_loss, indicators
                    FROM trades
                '''
                
                if pair:
                    query += ' WHERE pair = ?'
                    cursor.execute(query, (pair,))
                else:
                    cursor.execute(query)
                    
                results = cursor.fetchall()
                return [
                    {
                        'pair': row[0],
                        'timestamp': row[1],
                        'action': row[2],
                        'price': row[3],
                        'quantity': row[4],
                        'profit_loss': row[5],
                        'indicators': json.loads(row[6]) if row[6] else {}
                    }
                    for row in results
                ]
                
        except Exception as e:
            logging.error(f"Error getting trade history: {e}")
            return []

    def get_performance_metrics(self) -> Dict:
        """Get overall trading performance metrics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT COUNT(*) as total_trades,
                           SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                           SUM(profit_loss) as total_profit
                    FROM trades
                ''')
                
                row = cursor.fetchone()
                total_trades = row[0] or 0
                winning_trades = row[1] or 0
                total_profit = row[2] or 0
                
                return {
                    'total_trades': total_trades,
                    'winning_trades': winning_trades,
                    'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
                    'total_profit': total_profit
                }
                
        except Exception as e:
            logging.error(f"Error getting performance metrics: {e}")
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'win_rate': 0,
                'total_profit': 0
            }

    def clean_old_data(self, days: int = 30):
        """Clean up old trade data"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    DELETE FROM trades
                    WHERE timestamp < datetime('now', ? || ' days')
                ''', (str(-days),))
                
                conn.commit()
                
        except Exception as e:
            logging.error(f"Error cleaning old data: {e}")
