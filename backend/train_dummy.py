import pandas as pd
import numpy as np
import pickle
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
import os

def generate_data_and_model():
    print("Generating dummy data...")
    # Generate date range
    dates = pd.date_range(start="2024-01-01", periods=100, freq='D')
    
    # Generate synthetic usage data (kWh)
    # Base usage + Random noise + Weekly/Seasonality trend
    np.random.seed(42)
    usage = 10 + np.random.normal(0, 2, 100) + 5 * np.sin(np.linspace(0, 3.14 * 4, 100))
    usage = np.maximum(usage, 0.5) # Ensure no negative usage
    
    df = pd.DataFrame({'date': dates, 'usage': usage})
    
    # Save dummy dataset
    csv_path = "electricity_data.csv"
    df.to_csv(csv_path, index=False)
    print(f"Dummy data saved to {csv_path}")

    # Train Model
    print("Training model...")
    # Feature Engineering: Use previous day usage to predict next day
    df['prev_usage'] = df['usage'].shift(1)
    df = df.dropna()
    
    X = df[['prev_usage']]
    y = df['usage']
    
    model = LinearRegression()
    model.fit(X, y)
    
    # Save Model
    model_path = "electricity_model.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"Model saved to {model_path}")
    
    return csv_path, model_path

if __name__ == "__main__":
    generate_data_and_model()
