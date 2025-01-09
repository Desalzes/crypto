import sqlite3
import json
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'trading.db')
        self._init_db()
        
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                timestamp TEXT,
                pair TEXT,
                action TEXT,
                price REAL,
                quantity REAL,
                profit_loss REAL,
                indicators TEXT,
                timeframe TEXT
            );
        """)
        
        # Drop and recreate just indicator_performance table
        c.executescript("""
            DROP TABLE IF EXISTS indicator_performance;
            
            CREATE TABLE indicator_performance (
                pair TEXT,
                timeframe TEXT,
                indicator TEXT,
                success_rate REAL,
                total_trades INTEGER,
                last_updated TEXT,
                UNIQUE(pair, timeframe, indicator)
            );
        """)
        
        conn.commit()
        conn.close()

    def get_best_indicators(self, pair: str, timeframe: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            SELECT indicator, success_rate
            FROM indicator_performance
            WHERE pair = ? AND timeframe = ?
            AND total_trades >= 10
        """, (pair, timeframe))
        
        results = c.fetchall()
        conn.close()
        
        if not results:
            return {
                'RSI': 0.5,
                'MACD': 0.5,
                'BB': 0.5,
                'EMA': 0.5
            }
        
        return {row[0]: row[1] for row in results}

    def update_indicator_performance(self, pair: str, timeframe: str, 
                                   indicator: str, success: float, total: int):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute("""
                INSERT INTO indicator_performance (
                    pair, timeframe, indicator, success_rate, 
                    total_trades, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(pair, timeframe, indicator) DO UPDATE SET
                    success_rate = ((success_rate * total_trades) + ?) / (total_trades + ?),
                    total_trades = total_trades + ?,
                    last_updated = ?
            """, (
                pair, timeframe, indicator, success, total, 
                datetime.now().isoformat(),
                success, total, total, datetime.now().isoformat()
            ))
            
            conn.commit()
        except Exception as e:
            logger.error(f"Database error: {e}")
        finally:
            conn.close()