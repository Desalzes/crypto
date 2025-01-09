import requests
import json
import logging
from datetime import datetime
import numpy as np
import asyncio
import aiohttp
import sys
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class LLMAnalyzer:
    def __init__(self, config=None):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.config = config or {}
        
    async def analyze_indicators(self, market_data: dict) -> dict:
        try:
            prompt = self._create_detailed_prompt(market_data)
            response = await self._query_ollama(prompt)
            
            if response:
                analyzed_data = self._parse_response(response)
                if analyzed_data:
                    analyzed_data = self._validate_analysis(analyzed_data, market_data)
                    return analyzed_data
                    
            return self._default_response()
            
        except Exception as e:
            logger.error(f"LLM analysis error: {str(e)}")
            return self._default_response()

    def _create_detailed_prompt(self, market_data: dict) -> str:
        current_price = market_data.get('price', 'N/A')
        change_24h = market_data.get('change24h', 'N/A')
        indicators = market_data.get('technical_analysis', {})

        prompt = f"""Analyze the following market data for {market_data['symbol']} and provide a trading decision.

Current Market State:
Price: ${current_price}
24h Change: {change_24h}%

Technical Indicators:
{json.dumps(indicators, indent=2)}

Provide analysis in JSON format:
{{
    "indicator_analysis": {{
        "indicator_name": {{
            "value": 123.45,
            "signal": "BUY/SELL/NEUTRAL",
            "reliability": 0.85,
            "warning_signs": ["reason1", "reason2"]
        }}
    }},
    "execution_signals": {{
        "primary_action": "BUY/SELL/HOLD",
        "confidence": 0.75,
        "reasoning": ["factor1", "factor2"],
        "stop_loss": 123.45,
        "take_profit": [124.56, 125.67]
    }},
    "risk_metrics": {{
        "trade_risk": "LOW/MEDIUM/HIGH",
        "max_loss_potential": "2.5%",
        "risk_factors": ["factor1", "factor2"]
    }}
}}"""
        return prompt

    async def _query_ollama(self, prompt: str) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.ollama_url,
                    json={
                        "model": "mistral",
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=30
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('response', '')
            return None
        except Exception as e:
            logger.error(f"Ollama request failed: {str(e)}")
            return None

    def _parse_response(self, response: str) -> dict:
        try:
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            
            data = json.loads(response)
            
            required_fields = [
                'indicator_analysis',
                'execution_signals',
                'risk_metrics'
            ]
            
            if not all(field in data for field in required_fields):
                return None
                
            return data
            
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {str(e)}")
            return None

    def _validate_analysis(self, analysis: dict, market_data: dict) -> dict:
        try:
            signals = analysis['execution_signals']
            if 'primary_action' not in signals or signals['primary_action'] not in ['BUY', 'SELL', 'HOLD']:
                signals['primary_action'] = 'HOLD'
            
            if 'confidence' not in signals or not isinstance(signals['confidence'], (int, float)):
                signals['confidence'] = 0.0
            signals['confidence'] = min(1.0, max(0.0, signals['confidence']))
            
            risk = analysis['risk_metrics']
            if 'trade_risk' not in risk or risk['trade_risk'] not in ['LOW', 'MEDIUM', 'HIGH']:
                risk['trade_risk'] = 'HIGH'

            return analysis
            
        except Exception as e:
            logger.error(f"Error validating analysis: {str(e)}")
            return self._default_response()

    def _default_response(self) -> dict:
        return {
            "indicator_analysis": {},
            "execution_signals": {
                "primary_action": "HOLD",
                "confidence": 0.0,
                "reasoning": ["Analysis failed"],
                "stop_loss": None,
                "take_profit": []
            },
            "risk_metrics": {
                "trade_risk": "HIGH",
                "max_loss_potential": "3%",
                "risk_factors": ["Analysis failure"]
            }
        }