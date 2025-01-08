import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class StrategyAdjustor:
    def __init__(self, config_path: str = None):
        self.config_path = config_path or Path(__file__).parent.parent.parent / 'config' / 'indicators_config.json'
        self.config = self._load_config()
        
    def _load_config(self):
        """Load current indicator configuration."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}
            
    def _save_config(self):
        """Save updated configuration."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def adjust_indicator_params(self, indicator: str, params: dict):
        """Adjust parameters for a specific indicator."""
        if indicator not in self.config.get('indicators', {}):
            logger.warning(f"Indicator {indicator} not found in config")
            return False
            
        try:
            # Update parameters
            self.config['indicators'][indicator].update(params)
            self._save_config()
            return True
        except Exception as e:
            logger.error(f"Error adjusting indicator parameters: {e}")
            return False
    
    def adjust_timeframe_weights(self, timeframe: str, weight: float):
        """Adjust weight for a specific timeframe."""
        if 'timeframes' not in self.config:
            self.config['timeframes'] = {}
            
        try:
            self.config['timeframes'][timeframe] = weight
            self._save_config()
            return True
        except Exception as e:
            logger.error(f"Error adjusting timeframe weight: {e}")
            return False
    
    def parse_adjustment(self, adjustment: str):
        """Parse adjustment string into actionable changes."""
        try:
            if 'increase' in adjustment.lower() or 'decrease' in adjustment.lower():
                return self._parse_scaling_adjustment(adjustment)
            elif 'set' in adjustment.lower():
                return self._parse_direct_adjustment(adjustment)
            else:
                logger.warning(f"Could not parse adjustment: {adjustment}")
                return None
        except Exception as e:
            logger.error(f"Error parsing adjustment: {e}")
            return None
    
    def _parse_scaling_adjustment(self, adjustment: str):
        """Parse adjustments that scale values up or down."""
        words = adjustment.lower().split()
        try:
            if 'increase' in words:
                action = 'increase'
            else:
                action = 'decrease'
                
            # Find the percentage if specified
            scale = 0.1  # default 10%
            for i, word in enumerate(words):
                if word.endswith('%'):
                    try:
                        scale = float(word[:-1]) / 100
                        break
                    except ValueError:
                        continue
                        
            # Find what we're adjusting
            target = None
            for word in words:
                if any(s in word for s in ['period', 'length', 'window', 'threshold']):
                    target = word
                    break
                    
            if not target:
                return None
                
            return {
                'action': action,
                'scale': scale,
                'target': target
            }
            
        except Exception:
            return None
    
    def _parse_direct_adjustment(self, adjustment: str):
        """Parse adjustments that set specific values."""
        words = adjustment.lower().split()
        try:
            # Look for "set X to Y" pattern
            if 'set' in words and 'to' in words:
                set_idx = words.index('set')
                to_idx = words.index('to')
                
                if set_idx < to_idx and to_idx < len(words) - 1:
                    target = ' '.join(words[set_idx + 1:to_idx])
                    try:
                        value = float(words[to_idx + 1])
                    except ValueError:
                        value = words[to_idx + 1]
                        
                    return {
                        'action': 'set',
                        'target': target,
                        'value': value
                    }
                    
            return None
            
        except Exception:
            return None