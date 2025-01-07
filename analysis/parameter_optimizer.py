import json
import logging
import requests
from typing import Dict

class ParameterOptimizer:
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.logger = logging.getLogger(__name__)

    def optimize_parameters(self, symbol: str, timeframe: str, 
                          performance_data: Dict, current_params: Dict) -> Dict:
        try:
            prompt = (
                f"You are a crypto trading expert. Analyze these parameters and suggest optimizations:\n"
                f"Symbol: {symbol}\n"
                f"Timeframe: {timeframe}\n"
                f"Current Performance: {json.dumps(performance_data, indent=2)}\n"
                f"Current Parameters: {json.dumps(current_params, indent=2)}\n\n"
                "Return only a JSON object with the optimized parameters."
            )
            
            response = requests.post(
                self.ollama_url,
                json={"model": "mistral", "prompt": prompt},
                timeout=30
            )
            response.raise_for_status()
            result = response.json().get('response', '')
            return json.loads(result) if result else current_params
        except Exception as e:
            self.logger.error(f"Parameter optimization error: {e}")
            return current_params