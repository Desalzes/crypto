import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class StrategyAdjustor:
    def __init__(self, config_path: str = None):
        self.config_path = config_path or Path(__file__).parent.parent.parent / 'config' / 'indicators_config.json'
        self.config = self._load_config()
        self.minimum_reliability = 0.35  # Changed from 0.40 to 0.35