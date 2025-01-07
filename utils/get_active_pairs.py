import aiohttp
import asyncio
import json
import logging
import os
from typing import Dict, List

async def get_kraken_pairs() -> List[str]:
    # Create data directory if it doesn't exist
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)
    pairs_file = os.path.join(data_dir, 'kraken_usd_pairs.json')

    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.kraken.com/0/public/AssetPairs") as response:
            pairs_data = await response.json()
            if pairs_data.get('error'):
                logging.error(f"Kraken API error: {pairs_data['error']}")
                return []
            
        async with session.get("https://api.kraken.com/0/public/Ticker") as response:
            volume_data = await response.json()
            if volume_data.get('error'):
                logging.error(f"Kraken API error: {volume_data['error']}")
                return []

    pairs = []
    result = pairs_data.get('result', {})
    volumes = volume_data.get('result', {})

    for pair_name, pair_info in result.items():
        if pair_info['quote'] in ['ZUSD', 'USD']:
            try:
                volume_24h = float(volumes[pair_name]['v'][1])
                pairs.append({
                    'pair': pair_name,
                    'altname': pair_info['altname'],
                    'base': pair_info['base'],
                    'quote': pair_info['quote'],
                    'volume_24h': volume_24h
                })
            except (KeyError, ValueError, TypeError) as e:
                logging.warning(f"Error processing pair {pair_name}: {e}")
                continue

    pairs.sort(key=lambda x: x['volume_24h'], reverse=True)
    
    with open(pairs_file, 'w') as f:
        json.dump(pairs[:200], f, indent=2)
        
    return [p['altname'] for p in pairs[:200]]

if __name__ == "__main__":
    asyncio.run(get_kraken_pairs())