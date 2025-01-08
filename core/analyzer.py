from pathlib import Path
import requests
import json
import logging
from datetime import datetime
import numpy as np
import asyncio
import aiohttp
import sys
import os

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

class LLMAnalyzer:
    def __init__(self, config=None):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.config = config or {}
        self.db = DatabaseManager()
        self.base_indicators = ['RSI', 'MACD', 'Bollinger Bands']
        
        # Adjusted thresholds for more aggressive expansion
        self.initial_threshold = 0.45  # 45% for considering third indicator
        self.expansion_threshold = 0.55  # 55% for considering fourth indicator
        self.minimum_reliability = 0.40  # Won't consider indicators below 40%

    async def analyze_indicators(self, market_data: dict) -> dict:
        """Progressive indicator analysis."""
        try:
            # First analyze best performing pair
            best_pair = await self._analyze_initial_pairs(market_data)
            if not best_pair:
                return self._default_response()

            # If pair performs well, consider adding third indicator
            if best_pair['combined_reliability'] >= self.initial_threshold:
                enhanced_analysis = await self._expand_indicator_set(market_data, best_pair)
                if enhanced_analysis:
                    return enhanced_analysis

            # Return original pair analysis if expansion wasn't successful
            return best_pair['analysis']

        except Exception as e:
            logger.error(f"LLM analysis error: {str(e)}")
            return self._default_response()

    async def _analyze_initial_pairs(self, market_data: dict) -> dict:
        """Analyze initial indicator pairs."""
        pairs = [
            ('RSI', 'MACD'),
            ('RSI', 'Bollinger Bands'),
            ('MACD', 'Bollinger Bands')
        ]
        
        best_pair = None
        best_reliability = 0

        for pair in pairs:
            prompt = self._create_pair_analysis_prompt(market_data, pair)
            response = await self._query_ollama(prompt)
            
            if response:
                analysis = self._parse_response(response)
                if not analysis:
                    continue

                # Calculate combined reliability
                reliabilities = [
                    stats.get('reliability', 0)
                    for ind, stats in analysis.get('indicator_analysis', {}).items()
                ]
                combined_reliability = np.mean(reliabilities) if reliabilities else 0

                if combined_reliability > best_reliability:
                    best_reliability = combined_reliability
                    best_pair = {
                        'indicators': pair,
                        'analysis': analysis,
                        'combined_reliability': combined_reliability
                    }

        return best_pair

    async def _expand_indicator_set(self, market_data: dict, best_pair: dict) -> dict:
        """Consider adding additional indicators."""
        current_indicators = set(best_pair['indicators'])
        available_indicators = set(self.base_indicators) - current_indicators

        # Use different thresholds based on current set size
        threshold = (self.expansion_threshold 
                    if len(current_indicators) == 3 
                    else self.initial_threshold)

        expansion_decision = await self._should_add_indicator(
            market_data, best_pair, available_indicators
        )

        if not expansion_decision or not expansion_decision.get('should_add'):
            return None

        new_indicator_set = list(current_indicators) + [expansion_decision['indicator']]
        
        prompt = self._create_expanded_analysis_prompt(
            market_data, new_indicator_set, best_pair['analysis']
        )
        response = await self._query_ollama(prompt)
        
        if not response:
            return None
            
        expanded_analysis = self._parse_response(response)
        if not expanded_analysis:
            return None

        # Check if expansion improved the analysis
        expanded_reliabilities = [
            stats.get('reliability', 0)
            for ind, stats in expanded_analysis.get('indicator_analysis', {}).items()
        ]
        expanded_reliability = np.mean(expanded_reliabilities) if expanded_reliabilities else 0

        # Ensure all indicators meet minimum reliability
        if min(expanded_reliabilities) < self.minimum_reliability:
            return None

        # Small improvement threshold (1% for more aggressive expansion)
        min_improvement = 0.01
        if expanded_reliability > (best_pair['combined_reliability'] + min_improvement):
            # If third indicator was successful, consider fourth
            if (len(new_indicator_set) == 3 and 
                expanded_reliability >= self.expansion_threshold):
                fourth_indicator = await self._expand_indicator_set(
                    market_data,
                    {
                        'indicators': new_indicator_set,
                        'analysis': expanded_analysis,
                        'combined_reliability': expanded_reliability
                    }
                )
                if fourth_indicator:
                    return fourth_indicator

            return expanded_analysis

        return None

    async def _should_add_indicator(self, market_data: dict, best_pair: dict, available_indicators: set) -> dict:
        """Decide whether to add another indicator and which one."""
        prompt = f"""Analyze the current indicator combination and decide if adding another indicator would be beneficial.

Current Performance:
{json.dumps(best_pair['analysis'], indent=2)}

Available Indicators to Add: {list(available_indicators)}

Consider:
1. Current indicator reliability and correlation
2. Market conditions and volatility
3. Potential complementary indicators

Respond in JSON format:
{{
    "should_add": true/false,
    "indicator": "name of recommended indicator",
    "reasoning": "explanation"
}}
"""
        response = await self._query_ollama(prompt)
        if not response:
            return {'should_add': False}

        try:
            decision = json.loads(response)
            return decision
        except:
            return {'should_add': False}

    def _create_pair_analysis_prompt(self, data: dict, indicator_pair: tuple) -> str:
        """Create analysis prompt for an indicator pair."""
        return f"""Analyze this specific pair of indicators for {data.get('symbol')}:

Indicators: {indicator_pair[0]} and {indicator_pair[1]}

Current Market Data:
Symbol: {data.get('symbol')}
Price: ${data.get('price')}
Volume 24h: {data.get('volume')}

Technical Analysis:
{json.dumps(data.get('technical_analysis', {}), indent=2)}

Tasks:
1. Evaluate each indicator's reliability and interaction
2. Assess their combined effectiveness
3. Suggest parameter adjustments
4. Identify any concerning signals

Format your response as specified JSON."""

    def _create_expanded_analysis_prompt(self, data: dict, indicators: list, previous_analysis: dict) -> str:
        """Create analysis prompt for expanded indicator set."""
        return f"""Analyze this expanded set of indicators for {data.get('symbol')}:

Current Indicators: {', '.join(indicators)}

Previous Analysis:
{json.dumps(previous_analysis, indent=2)}

Current Market Data:
Symbol: {data.get('symbol')}
Price: ${data.get('price')}
Volume 24h: {data.get('volume')}

Technical Analysis:
{json.dumps(data.get('technical_analysis', {}), indent=2)}

Tasks:
1. Evaluate how the new indicator complements existing ones
2. Assess overall effectiveness of the expanded set
3. Suggest parameter adjustments
4. Identify any conflicting signals

Format your response exactly like this:
{{
    "indicator_analysis": {{
        "indicator_name": {{
            "reliability": 0.0 to 1.0,
            "suggested_changes": "description",
            "concerns": ["list", "of", "concerns"]
        }}
    }},
    "pattern_recommendations": [
        {{
            "pattern": "description",
            "reasoning": "explanation",
            "confidence": 0.0 to 1.0
        }}
    ],
    "strategy_adjustments": [
        "list of specific changes to make"
    ],
    "summary": "brief explanation of findings"
}}"""

    async def _query_ollama(self, prompt: str) -> str:
        """Query Ollama LLM with retries."""
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                response = await self._make_ollama_request(prompt)
                return response
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to query Ollama after {max_retries} attempts: {e}")
                    return None
                logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                await asyncio.sleep(retry_delay)
        
        return None

    def _make_ollama_request(self, prompt: str) -> str:
        """Make an HTTP request to Ollama."""
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": "mistral",
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json().get('response', '')
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ollama request failed: {str(e)}")

    def _parse_response(self, response: str) -> dict:
        """Parse and validate LLM response."""
        try:
            cleaned_response = response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            
            data = json.loads(cleaned_response)
            
            # Validate required fields
            required_fields = ['indicator_analysis', 'pattern_recommendations', 
                             'strategy_adjustments', 'summary']
            if not all(field in data for field in required_fields):
                logger.error("Missing required fields in LLM response")
                return self._default_response()
                
            return data
            
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response")
            return self._default_response()
    
    def _default_response(self) -> dict:
        """Default response when analysis fails."""
        return {
            "indicator_analysis": {},
            "pattern_recommendations": [],
            "strategy_adjustments": [],
            "summary": "Analysis failed, using default response"
        }