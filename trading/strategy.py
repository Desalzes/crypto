import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.technical_indicators import TechnicalAnalysis
from analysis.llm_analyzer import LLMAnalyzer
from market_data.news_fetcher import NewsFetcher

class TradingStrategy:
    def __init__(self, api_key: str):
        self.analysis = TechnicalAnalysis()
        self.llm = LLMAnalyzer()
        self.news = NewsFetcher(api_key)
        
    async def analyze_symbol(self, symbol: str, price_data: dict, intraday_data=None) -> dict:
        # Get technical analysis
        ta_signals = self.analysis.analyze_price_action(intraday_data)
        
        # Get news
        news_data = await self.news.get_news(symbol)
        
        # Prepare data for LLM
        market_data = {
            "symbol": symbol,
            "price": price_data["price"],
            "change_percent": price_data["change_percent"],
            "volume": price_data["volume"],
            "technical": ta_signals,
            "news": news_data
        }
        
        # Get LLM analysis
        llm_decision = self.llm.analyze_market_data(market_data)
        
        return {
            "symbol": symbol,
            "action": llm_decision["action"],
            "confidence": llm_decision["confidence"],
            "reasoning": llm_decision["reasoning"],
            "risk_level": llm_decision["risk_level"],
            "technical_data": ta_signals,
            "latest_news": news_data
        }
    
    def calculate_position_size(self, portfolio_value: float, confidence: float, 
                              risk_level: str) -> float:
        base_risk = {
            "LOW": 0.02,
            "MEDIUM": 0.015,
            "HIGH": 0.01
        }.get(risk_level, 0.01)
        
        return portfolio_value * base_risk * confidence