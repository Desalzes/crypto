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
        self.timeout = 10
        self.max_retries = 2
        
    async def analyze_indicators(self, market_data: dict) -> dict:
        try:
            # First try to get analysis without LLM
            analyzed_data = self._analyze_without_llm(market_data)
            if analyzed_data:
                return analyzed_data

            # If needed, try LLM with retries
            for attempt in range(self.max_retries):
                prompt = self._create_detailed_prompt(market_data)
                response = await self._query_ollama(prompt)
                
                if response:
                    analyzed_data = self._parse_response(response)
                    if analyzed_data:
                        analyzed_data = self._validate_analysis(analyzed_data, market_data)
                        return analyzed_data
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
                    
            return self._default_response()
            
        except Exception as e:
            logger.error(f"LLM analysis error: {str(e)}")
            return self._default_response()

    def _analyze_without_llm(self, market_data: dict) -> dict:
        """Quick analysis without LLM"""
        try:
            indicators = market_data.get('technical_analysis', {})
            
            # Simple rule-based analysis
            rsi = indicators.get('rsi', 50)
            macd = indicators.get('macd', 0)
            macd_signal = indicators.get('macd_signal', 0)
            
            # Determine action
            if rsi < 30 and macd > macd_signal:
                action = "BUY"
                confidence = 0.7
            elif rsi > 70 and macd < macd_signal:
                action = "SELL"
                confidence = 0.7
            else:
                action = "HOLD"
                confidence = 0.5

            return {
                "indicator_analysis": {
                    "RSI": {
                        "value": rsi,
                        "signal": action,
                        "reliability": 0.8,
                        "warning_signs": []
                    }
                },
                "execution_signals": {
                    "primary_action": action,
                    "confidence": confidence,
                    "reasoning": ["Quick technical analysis"],
                    "stop_loss": market_data.get('price', 0) * 0.95,
                    "take_profit": [market_data.get('price', 0) * 1.05]
                },
                "risk_metrics": {
                    "trade_risk": "MEDIUM",
                    "max_loss_potential": "5%",
                    "risk_factors": ["Technical-based trade"]
                }
            }
        except Exception as e:
            logger.error(f"Quick analysis error: {str(e)}")
            return None

    async def _query_ollama(self, prompt: str) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.ollama_url,
                    json={
                        "model": "mistral:7b",
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,  # Low temperature for more consistent outputs
                            "top_p": 0.9,
                            "num_ctx": 2048,     # Context window size
                            "repeat_penalty": 1.1
                        }
                    },
                    timeout=self.timeout
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('response', '')
            return None
        except asyncio.TimeoutError:
            logger.warning("Ollama request timed out")
            return None
        except Exception as e:
            logger.error(f"Ollama request failed: {str(e)}")
            return None

    def _create_detailed_prompt(self, market_data: dict) -> str:
        current_price = market_data.get('price', 'N/A')
        change_24h = market_data.get('change24h', 'N/A')
        indicators = market_data.get('technical_analysis', {})

        prompt = f"""You are a cryptocurrency trading expert. Based on the market data, provide a trading analysis in JSON format ONLY. No other text or explanation.

Market Data for {market_data['symbol']}:
Price: ${current_price}
24h Change: {change_24h}%
Technical Indicators: {json.dumps(indicators, indent=2)}

Response format:
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