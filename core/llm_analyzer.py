import requests
import json
import logging

logger = logging.getLogger(__name__)

class LLMAnalyzer:
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        
    def analyze_market_data(self, data: dict) -> dict:
        try:
            prompt = self._create_market_prompt(data)
            response = self._query_ollama(prompt)
            if response:
                return self._parse_response(response)
            return self._default_response()
        except Exception as e:
            logger.error(f"LLM analysis error: {str(e)}")
            return self._default_response()
    
    def _create_market_prompt(self, data: dict) -> str:
        return f"""Your task is to analyze this market data as a professional trader and provide a clear trading decision.

Symbol: {data['symbol']}
Price: ${data.get('price', 'N/A')}
Change: {data.get('change_percent', 'N/A')}
Volume: {data.get('volume', 'N/A')}

Make a trading decision and format your response exactly like this:
{{
    "action": "BUY or SELL or HOLD",
    "confidence": 0.1 to 1.0,
    "reasoning": "brief explanation",
    "risk_level": "LOW or MEDIUM or HIGH"
}}"""
    
    def _query_ollama(self, prompt: str) -> str:
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": "mistral",
                    "prompt": prompt
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json().get('response', '')
        except requests.exceptions.ConnectionError:
            logger.error("Could not connect to Ollama. Is it running?")
            return None
        except Exception as e:
            logger.error(f"Ollama query error: {e}")
            return None

    def _parse_response(self, response: str) -> dict:
        try:
            return json.loads(response)
        except:
            logger.error("Failed to parse LLM response")
            return self._default_response()
            
    def _default_response(self) -> dict:
        return {
            "action": "HOLD",
            "confidence": 0.0,
            "reasoning": "LLM analysis unavailable",
            "risk_level": "HIGH"
        }