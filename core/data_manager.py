import sqlite3
import json
from datetime import datetime
import os
import logging
from typing import Dict

class DataManager:
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.dirname(__file__))
        self.db_path = os.path.join(self.script_dir, '../core/database', 'trading.db')
        self.trades_file = os.path.join(self.script_dir, '../core/database', 'trade_history.json')
        self.trades = []
        self.daily_stats = {}
        self._init_db()
        self.load_history()