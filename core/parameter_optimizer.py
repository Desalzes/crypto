"""Previous imports and class definition remain the same..."""

def _create_analysis_prompt(self, pair: str, data: Dict, current_params: Dict) -> str:
    return f"""You are a high-frequency crypto trading expert focusing on real-time parameter optimization for {pair}. Your goal is to fine-tune trading parameters for maximum efficiency in rapid market conditions.

Real-Time Market State:
Price: ${data.get('price', 'N/A')}
24h Volume: {data.get('volume24h', 'N/A')}
24h Change: {data.get('change24h', 'N/A')}%

Technical Indicators State:
{json.dumps(data.get('indicators', {}), indent=2)}

Current Parameter Configuration:
{json.dumps(current_params, indent=2)}

High-Frequency Trading Context:
1. Parameters must adapt to micro-market structure
2. Execution speed is critical
3. Higher noise levels in shorter timeframes
4. Quick adaptation to volatility changes
5. Risk management parameterization
6. Market depth considerations
7. Order flow dynamics
8. Cross-exchange arbitrage potential

Required Analysis:
1. Rapid Parameter Adaptation
   - Identify parameters that need immediate adjustment
   - Suggest modifications based on current market microstructure
   - Consider execution latency impact

2. Indicator Effectiveness
   - Evaluate each indicator's performance in current market conditions
   - Assess reliability in high-frequency context
   - Suggest timeframe-specific adjustments

3. Real-Time Optimization Targets
   - Entry/exit timing improvement
   - False signal reduction
   - Slippage minimization
   - Execution cost optimization

4. Risk Parameter Calibration
   - Position size optimization
   - Stop-loss placement efficiency
   - Take-profit level optimization
   - Risk-reward ratio maintenance

Return a detailed JSON analysis with this structure:
{
    "market_microstructure": {
        "conditions": ["list of current market microstructure conditions"],
        "volatility_state": {
            "level": "LOW/MEDIUM/HIGH",
            "trend": "INCREASING/DECREASING/STABLE",
            "requires_adjustment": true/false
        },
        "execution_environment": {
            "liquidity_quality": "description",
            "spread_analysis": "tight/wide/normal",
            "immediate_concerns": ["list", "of", "issues"]
        }
    },
    "indicator_optimization": {
        "indicator_name": {
            "current_effectiveness": 0.0 to 1.0,
            "noise_level": "LOW/MEDIUM/HIGH",
            "suggested_parameters": {
                "param_name": value,
                "reasoning": "explanation"
            },
            "weight_adjustment": {
                "action": "INCREASE/DECREASE/MAINTAIN",
                "magnitude": 0.0 to 0.2,
                "reasoning": "explanation"
            }
        }
    },
    "real_time_adjustments": [
        {
            "parameter": "name",
            "current_value": value,
            "suggested_value": value,
            "adjustment_reason": "detailed explanation",
            "priority_level": "HIGH/MEDIUM/LOW",
            "implementation_speed": "IMMEDIATE/GRADUAL"
        }
    ],
    "risk_framework_updates": {
        "position_sizing": {
            "current_modifier": value,
            "suggested_modifier": value,
            "adjustment_reason": "explanation"
        },
        "stop_loss_config": {
            "current_settings": {},
            "suggested_settings": {},
            "reasoning": "explanation"
        },
        "take_profit_structure": {
            "current_levels": [],
            "suggested_levels": [],
            "adaptation_reason": "explanation"
        }
    }
}

Prioritize parameters that impact IMMEDIATE trading performance and risk management in a high-frequency environment."""
    
    return prompt