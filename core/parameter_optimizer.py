import json
import logging
import requests
from typing import Dict, List, Optional

class ParameterOptimizer:
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.logger = logging.getLogger(__name__)
        self.pair_profiles = {}

    async def analyze_indicators(self, pair: str, data: Dict, current_params: Dict) -> Dict:
        try:
            prompt = self._create_analysis_prompt(pair, data, current_params)
            response = await self._query_ollama(prompt)
            
            if not response:
                return current_params
                
            analysis = self._parse_response(response)
            
            if not analysis:
                return current_params
                
            self.pair_profiles[pair] = analysis
            return self._adjust_parameters(current_params, analysis)
            
        except Exception as e:
            self.logger.error(f"Indicator analysis error for {pair}: {e}")
            return current_params

    def _create_analysis_prompt(self, pair: str, data: Dict, current_params: Dict) -> str:
        return f"""Analyze these indicators for {pair} as a professional crypto trader:

Current Market Data:
Price: ${data.get('price', 'N/A')}
24h Volume: {data.get('volume24h', 'N/A')}
24h Change: {data.get('change24h', 'N/A')}%

Technical Indicators:
{json.dumps(data.get('indicators', {}), indent=2)}

Current Parameters:
{json.dumps(current_params, indent=2)}

Tasks:
1. Analyze each indicator's effectiveness
2. Suggest parameter adjustments
3. Identify market conditions impacting indicators
4. Recommend weight adjustments

Return a JSON object with this structure:
{{
    "market_analysis": {{
        "conditions": ["list of current market conditions"],
        "volatility": "LOW/MEDIUM/HIGH",
        "trend": "BULLISH/BEARISH/SIDEWAYS"
    }},
    "indicator_analysis": {{
        "indicator_name": {{
            "effectiveness": 0.0 to 1.0,
            "suggested_params": {{}},
            "weight_adjustment": "INCREASE/DECREASE/MAINTAIN"
        }}
    }},
    "parameter_recommendations": [
        {{
            "param": "name",
            "current": value,
            "suggested": value,
            "reasoning": "explanation"
        }}
    ]
}}"""

    async def _query_ollama(self, prompt: str) -> Optional[str]:
        try:
            response = requests.post(
                self.ollama_url,
                json={"model": "mistral", "prompt": prompt},
                timeout=30
            )
            response.raise_for_status()
            return response.json().get('response', '')
        except Exception as e:
            self.logger.error(f"Ollama query error: {e}")
            return None

    def _parse_response(self, response: str) -> Optional[Dict]:
        try:
            if response.startswith("```json"):
                response = response[7:-3]
            return json.loads(response)
        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {e}")
            return None

    def _adjust_parameters(self, current_params: Dict, analysis: Dict) -> Dict:
        adjusted = current_params.copy()
        
        for rec in analysis.get('parameter_recommendations', []):
            param = rec.get('param')
            suggested = rec.get('suggested')
            if param and suggested:
                # Limit parameter changes to 20% per adjustment
                if isinstance(suggested, (int, float)):
                    current = rec.get('current', adjusted.get(param, suggested))
                    max_change = current * 0.2
                    change = suggested - current
                    change = max(min(change, max_change), -max_change)
                    adjusted[param] = current + change
                else:
                    adjusted[param] = suggested

        for ind, details in analysis.get('indicator_analysis', {}).items():
            if ind in adjusted.get('indicators', {}):
                weight_adj = details.get('weight_adjustment')
                current_weight = adjusted['indicators'][ind].get('weight', 0.5)
                
                if weight_adj == "INCREASE":
                    adjusted['indicators'][ind]['weight'] = min(1.0, current_weight * 1.1)
                elif weight_adj == "DECREASE":
                    adjusted['indicators'][ind]['weight'] = max(0.1, current_weight * 0.9)

        return adjusted

    def get_pair_profile(self, pair: str) -> Optional[Dict]:
        return self.pair_profiles.get(pair)
