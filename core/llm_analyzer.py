"""Previous imports remain the same..."""

def _create_market_prompt(self, data: dict) -> str:
    return f"""You are a specialized high-frequency cryptocurrency trading AI. Analyze this real-time market data for {data['symbol']} and provide an immediate trading decision optimized for quick execution.

Real-Time Market State:
Price: ${data.get('price', 'N/A')}
24h Change: {data.get('change_percent', 'N/A')}%
Volume Profile: {data.get('volume', 'N/A')}

High-Frequency Trading Context:
- Analysis timeframe: Minutes to hours
- Focus on executable signals
- Price action and momentum priority
- Rapid pattern recognition
- Immediate risk assessment
- Quick position sizing

Key Considerations:
1. Market Microstructure
   - Order flow dynamics
   - Liquidity conditions
   - Spread analysis
   - Volume profile

2. Technical State
   - Momentum readings
   - Price action patterns
   - Support/resistance levels
   - Volatility state

3. Risk Metrics
   - Volatility-adjusted position sizing
   - Precise stop-loss levels
   - Multiple take-profit targets
   - Risk-reward optimization

Provide an IMMEDIATE trading decision in this JSON format:
{
    "execution_signals": {
        "primary_action": "BUY or SELL or HOLD",
        "confidence": 0.1 to 1.0,
        "reasoning": [
            "list of key decision factors",
            "immediate catalysts",
            "critical concerns"
        ],
        "entry_parameters": {
            "suggested_entry": "price level",
            "stop_loss": "price level",
            "take_profit_targets": [
                "multiple price levels"
            ],
            "position_size_modifier": 0.1 to 1.0
        }
    },
    "market_context": {
        "volatility_state": "LOW/MEDIUM/HIGH",
        "trend_strength": 0.1 to 1.0,
        "momentum_quality": "WEAK/MODERATE/STRONG",
        "execution_urgency": "LOW/MEDIUM/HIGH"
    },
    "risk_assessment": {
        "level": "LOW/MEDIUM/HIGH",
        "key_factors": [
            "list of risk considerations"
        ],
        "max_loss_potential": "percentage",
        "suggested_leverage": 1.0 to 5.0
    }
}"""

    # Rest of the class implementation remains the same...
