from abc import ABC, abstractmethod
from typing import Dict, List, Optional

class MarketDataFeed(ABC):
    """Base class for market data feeds."""
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get current ticker data for a symbol."""
        pass
        
    @abstractmethod
    async def get_all_timeframe_data(self, symbol: str) -> Dict:
        """Get OHLCV data for all required timeframes."""
        pass
        
    @abstractmethod
    async def get_active_pairs(self) -> List[str]:
        """Get list of active trading pairs."""
        pass
        
    @abstractmethod
    async def close(self):
        """Close any open connections."""
        pass