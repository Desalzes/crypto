import asyncio
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib
import os
import time
from market_data.kraken_feed import KrakenFeed
from analysis.indicators import Indicators
import logging
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv

class ModelTrainer:
    def __init__(self, market_type="crypto"):
        load_dotenv()
        self.feed = KrakenFeed(
            api_key=os.getenv('KRAKEN_API_KEY'),
            secret_key=os.getenv('KRAKEN_SECRET_KEY')
        )
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = os.path.join(script_dir, 'data', 'historical')
        self.model_dir = os.path.join(script_dir, 'models')
        self.market_type = market_type
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.model_dir, exist_ok=True)
        
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        
    def _get_data_filepath(self, pair: str, timeframe: str) -> str:
        """Generate standardized filepath for historical data"""
        return os.path.join(self.data_dir, f"{pair}_{timeframe}_historical.csv")
        
    def _validate_ohlc_data(self, df: pd.DataFrame) -> bool:
        """Validate OHLC data for common issues"""
        if df.empty:
            return False
            
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_columns):
            logging.error(f"Missing required columns. Found: {df.columns.tolist()}")
            return False
            
        # Check for NaN values
        nan_counts = df[required_columns].isna().sum()
        if nan_counts.any():
            logging.error(f"Found NaN values: {nan_counts[nan_counts > 0]}")
            return False
            
        # Validate price relationships
        invalid_prices = df[
            (df['high'] < df['low']) | 
            (df['close'] < df['low']) | 
            (df['close'] > df['high']) |
            (df['open'] < df['low']) |
            (df['open'] > df['high'])
        ]
        if not invalid_prices.empty:
            logging.error(f"Found {len(invalid_prices)} rows with invalid price relationships")
            return False
            
        # Check for duplicates
        duplicates = df[df.duplicated(subset=['timestamp'])]
        if not duplicates.empty:
            logging.error(f"Found {len(duplicates)} duplicate timestamps")
            return False
            
        return True

    async def _fetch_chunk(self, pair: str, interval: int, chunk_size: int, since_timestamp: int) -> pd.DataFrame:
        """Fetch a single chunk of historical data with validation"""
        try:
            ohlc = await self.feed.get_historical_data(pair, interval, chunk_size, since_timestamp)
            if ohlc is not None and not ohlc.empty:
                if self._validate_ohlc_data(ohlc):
                    return ohlc
                else:
                    logging.error(f"Invalid data received for {pair} from timestamp {since_timestamp}")
                    return pd.DataFrame()
        except Exception as e:
            logging.error(f"Error fetching chunk for {pair}: {e}")
        return pd.DataFrame()

    def load_cached_data(self, pair: str, timeframe: str) -> pd.DataFrame:
        """Load historical data from cache if it exists"""
        filepath = self._get_data_filepath(pair, timeframe)
        if os.path.exists(filepath):
            try:
                df = pd.read_csv(filepath)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                if self._validate_ohlc_data(df):
                    return df.sort_values('timestamp')
                else:
                    logging.error(f"Cached data validation failed for {pair}_{timeframe}")
                    # Backup invalid data before returning empty DataFrame
                    backup_path = filepath + f".invalid_{int(time.time())}"
                    df.to_csv(backup_path, index=False)
                    logging.info(f"Backed up invalid data to {backup_path}")
            except Exception as e:
                logging.error(f"Error loading cached data for {pair}_{timeframe}: {e}")
        return pd.DataFrame()

    def append_to_cache(self, pair: str, timeframe: str, new_data: pd.DataFrame):
        """Append new data to cache, maintaining uniqueness and sorting"""
        if new_data.empty:
            return
            
        filepath = self._get_data_filepath(pair, timeframe)
        try:
            # Load existing data if any
            existing_data = self.load_cached_data(pair, timeframe)
            
            if existing_data.empty:
                # No existing data, just save new data
                new_data.to_csv(filepath, index=False)
                logging.info(f"Saved {len(new_data)} new candles to {filepath}")
            else:
                # Combine existing and new data
                combined_data = pd.concat([existing_data, new_data])
                # Remove duplicates keeping the newer data
                combined_data = combined_data.drop_duplicates(
                    subset=['timestamp'], 
                    keep='last'
                ).sort_values('timestamp')
                
                if self._validate_ohlc_data(combined_data):
                    # Create a backup of the old file
                    backup_path = filepath + f".backup_{int(time.time())}"
                    os.rename(filepath, backup_path)
                    
                    # Save the new combined data
                    combined_data.to_csv(filepath, index=False)
                    logging.info(f"Appended {len(new_data)} candles to {filepath}")
                    logging.info(f"Total records: {len(combined_data)}")
                    
                    # Remove backup if save was successful
                    os.remove(backup_path)
                else:
                    logging.error("Failed to validate combined data, keeping existing data")
                    
        except Exception as e:
            logging.error(f"Error appending data to cache for {pair}_{timeframe}: {e}")

    async def update_historical_data(self, pair: str, timeframe_info: dict) -> pd.DataFrame:
        """Update historical data, fetching only new data if cache exists"""
        tf_name = f"{timeframe_info['interval']}m"
        cached_data = self.load_cached_data(pair, tf_name)
        
        # Calculate the timestamp to start fetching from
        if not cached_data.empty:
            last_timestamp = cached_data['timestamp'].max()
            start_timestamp = int(last_timestamp.timestamp())
            logging.info(f"Found cached data for {pair}_{tf_name} up to {last_timestamp}")
        else:
            # If no cached data, fetch the full historical period
            start_timestamp = int((datetime.now() - timedelta(days=timeframe_info['days'])).timestamp())
        
        # Fetch new data in chunks
        chunk_size = 5000
        new_chunks = []
        current_timestamp = start_timestamp

        while True:
            chunk = await self._fetch_chunk(pair, timeframe_info['interval'], chunk_size, current_timestamp)
            if chunk.empty:
                break
                
            new_chunks.append(chunk)
            logging.info(f"Downloaded chunk of {len(chunk)} candles for {pair}_{tf_name}")
            
            # Update timestamp for next chunk
            current_timestamp = int(chunk['timestamp'].max().timestamp())
            
            # Rate limiting
            await asyncio.sleep(1)
            
            # Break if we've reached recent data
            if current_timestamp > int(datetime.now().timestamp() - 300):  # 5 minutes ago
                break
        
        if new_chunks:
            # Combine new chunks
            new_data = pd.concat(new_chunks)
            new_data = new_data.drop_duplicates(subset=['timestamp']).sort_values('timestamp')
            
            # Append to cache
            self.append_to_cache(pair, tf_name, new_data)
            
            # Return combined data for training
            if not cached_data.empty:
                return pd.concat([cached_data, new_data]).drop_duplicates(
                    subset=['timestamp']
                ).sort_values('timestamp')
            return new_data
        
        return cached_data

    async def download_training_data(self):
        """Download historical data for all major pairs with improved caching"""
        pairs = await self.feed.get_active_pairs()
        pairs = pairs[:14]  # Top pairs only
        
        # Define timeframes with longer historical periods
        timeframes = {
            '1m': {'interval': 1, 'days': 30},    # 1 month of 1m data
            '5m': {'interval': 5, 'days': 90},    # 3 months of 5m data
            '15m': {'interval': 15, 'days': 180}  # 6 months of 15m data
        }
        
        all_data = {}
        for pair in pairs:
            try:
                pair_data = {}
                for tf_name, tf_info in timeframes.items():
                    logging.info(f"Processing {tf_name} data for {pair}...")
                    
                    # Update historical data with caching
                    data = await self.update_historical_data(pair, tf_info)
                    
                    if not data.empty:
                        pair_data[tf_name] = data
                        logging.info(f"Successfully processed {len(data)} candles for {pair} {tf_name}")
                
                if pair_data:
                    all_data[pair] = pair_data
                    logging.info(f"Completed downloading data for {pair}")
                
            except Exception as e:
                logging.error(f"Error processing data for {pair}: {e}")
                continue
                
        return all_data
                
    def prepare_features(self, data):
        """Create features from OHLC data with technical indicators"""
        features = []
        labels = []
        
        for pair, timeframes in data.items():
            for tf, df in timeframes.items():
                if df is None or df.empty:
                    continue
                    
                # Calculate technical indicators
                indicators = Indicators.calculate_all(df, tf)
                
                # Create feature set
                feature_set = pd.DataFrame({
                    'rsi': indicators['rsi'],
                    'macd': indicators['macd'],
                    'macd_signal': indicators['macd_signal'],
                    'bb_upper': indicators['bb_upper'],
                    'bb_lower': indicators['bb_lower'],
                    'ema_short': indicators['ema_short'],
                    'ema_long': indicators['ema_long'],
                    'tenkan_sen': indicators['tenkan_sen'],
                    'kijun_sen': indicators['kijun_sen'],
                    'volume': df['volume'],
                    'close': df['close'],
                    'high': df['high'],
                    'low': df['low']
                })
                
                # Calculate future returns for labels
                future_returns = df['close'].pct_change(5).shift(-5)  # 5-period future returns
                
                # Create labels: 1 for positive returns, 0 for negative
                labels_array = (future_returns > 0).astype(int)
                
                # Remove rows with NaN values
                valid_idx = ~(feature_set.isna().any(axis=1) | labels_array.isna())
                features.append(feature_set[valid_idx])
                labels.append(labels_array[valid_idx])
                
        return pd.concat(features), pd.concat(labels)
        
    def train_model(self, features, labels):
        """Train and save the model"""
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            features, labels, test_size=0.2, random_state=42
        )
        
        # Train model
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42
        )
        
        model.fit(X_train, y_train)
        
        # Save model and feature names
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        model_path = os.path.join(self.model_dir, f'market_model_{self.market_type}_{timestamp}.joblib')
        feature_path = os.path.join(self.model_dir, f'feature_names_{self.market_type}_{timestamp}.json')
        
        joblib.dump(model, model_path)
        with open(feature_path, 'w') as f:
            json.dump(list(features.columns), f)
            
        # Calculate and log performance metrics
        train_score = model.score(X_train, y_train)
        test_score = model.score(X_test, y_test)
        
        logging.info(f"Model trained successfully:")
        logging.info(f"Training accuracy: {train_score:.4f}")
        logging.info(f"Test accuracy: {test_score:.4f}")
        logging.info(f"Total training samples: {len(features)}")
        
        return model_path, feature_path