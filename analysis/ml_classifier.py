import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import pandas as pd
import json
import logging
import os

class MLModel(nn.Module):
    def __init__(self, input_size):
        super(MLModel, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_size, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 2)
        )
    
    def forward(self, x):
        return self.network(x)

class MarketClassifier:
    def __init__(self, model_path="models/crypto_model.pt"):
        self.model_path = model_path
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.feature_names = None
        self.scaler = None
        try:
            self._load_model()
        except Exception as e:
            logging.error(f"Error loading model: {e}")

    def _load_model(self):
        if os.path.exists(self.model_path):
            checkpoint = torch.load(self.model_path)
            self.model = MLModel(checkpoint['input_size']).to(self.device)
            self.model.load_state_dict(checkpoint['model_state'])
            self.feature_names = checkpoint['feature_names']
            self.scaler = checkpoint['scaler']

    def train(self, data: pd.DataFrame) -> None:
        features, labels = self._prepare_features(data)
        input_size = features.shape[1]
        
        X = torch.FloatTensor(features).to(self.device)
        y = torch.LongTensor(labels).to(self.device)
        
        self.model = MLModel(input_size).to(self.device)
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(self.model.parameters())
        
        batch_size = 32
        epochs = 50
        
        for epoch in range(epochs):
            for i in range(0, len(X), batch_size):
                batch_X = X[i:i+batch_size]
                batch_y = y[i:i+batch_size]
                
                optimizer.zero_grad()
                outputs = self.model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
        
        os.makedirs("models", exist_ok=True)
        torch.save({
            'model_state': self.model.state_dict(),
            'input_size': input_size,
            'feature_names': self.feature_names,
            'scaler': self.scaler
        }, self.model_path)

    def predict(self, data: pd.DataFrame) -> float:
        if self.model is None or data.empty:
            return 0.5
        try:
            features = self._prepare_prediction_features(data)
            X = torch.FloatTensor(features).to(self.device)
            with torch.no_grad():
                outputs = self.model(X)
                probabilities = torch.softmax(outputs, dim=1)
                return probabilities[0][1].item()
        except Exception as e:
            logging.error(f"Prediction error: {e}")
            return 0.5

    def _prepare_features(self, data):
        # Your existing feature preparation code
        pass