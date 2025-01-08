import json
import logging
import requests
from typing import Dict, Optional, Union, List
from pathlib import Path
import asyncio

logger = logging.getLogger(__name__)

class StrategyOptimizer:
    def __init__(self, config_path: str = None):
        self.config_path = config_path or Path(__file__).parent.parent / 'config' / 'indicators_config.json'
        self.ollama_url = "http://localhost:11434/api/generate"
        self.config = self._load_config()