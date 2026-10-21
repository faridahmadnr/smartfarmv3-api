"""
ML Model Loader untuk SmartFarm API
"""
import joblib
import numpy as np
from pathlib import Path
from scipy.stats import kurtosis, skew

# Path ke trained models
MODEL_DIR = Path(__file__).parent / "trained_models"

# Load models saat startup
classification_model = None
classification_scaler = None
forecasting_model = None
forecasting_config = None

def load_models():
    """Load semua trained models"""
    global classification_model, classification_scaler, forecasting_model, forecasting_config
    
    try:
        classification_model = joblib.load(MODEL_DIR / "classification_rf.joblib")
        classification_scaler = joblib.load(MODEL_DIR / "scaler_classification.joblib")
        forecasting_model = joblib.load(MODEL_DIR / "forecasting_xgb.joblib")
        forecasting_config = joblib.load(MODEL_DIR / "forecasting_config.joblib")
        print("✅ ML Models loaded successfully")
    except Exception as e:
        print(f"⚠️  Model loading error: {e}")
        print("Run export_models.py first!")

def predict_classification(features: dict) -> dict:
    """
    Prediksi klasifikasi (Normal/Abnormal)
    
    Args:
        features: Dict dengan keys: Hari Ke-, Suhu, Kelembaban, Amoniak,
                  Pakan, Minum, Bobot, Populasi, Luas Kandang, Hour
    
    Returns:
        {
            'class': 'Normal' atau 'Abnormal',
            'probability': float,
            'confidence': float
        }
    """
    if classification_model is None:
        load_models()
    
    # Extract features dalam urutan yang benar
    hour = features['Hour']
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)
    
    X = np.array([[
        features['Hari Ke-'],
        features['Suhu'],
        features['Kelembaban'],
        features['Amoniak'],
        features['Pakan'],
        features['Minum'],
        features['Bobot'],
        features['Populasi'],
        features['Luas Kandang'],
        hour_sin,
        hour_cos
    ]])
    
    # Scale
    X_scaled = classification_scaler.transform(X)
    
    # Predict
    pred_class = classification_model.predict(X_scaled)[0]
    pred_proba = classification_model.predict_proba(X_scaled)[0]
    
    return {
        'class': 'Abnormal' if pred_class == 1 else 'Normal',
        'probability': float(pred_proba[pred_class]),
        'confidence': float(max(pred_proba))
    }

def stats_features_single(input_data):
    """Calculate statistical features untuk 1 window"""
    min_val = float(np.min(input_data))
    max_val = float(np.max(input_data))
    diff = max_val - min_val
    std = float(np.std(input_data))
    mean = float(np.mean(input_data))
    median = float(np.median(input_data))
    kurt = float(kurtosis(input_data))
    sk = float(skew(input_data))
    
    return np.append(input_data, [min_val, max_val, diff, std, mean, median, kurt, sk])

def predict_forecasting(sensor_history: list) -> dict:
    """
    Prediksi jumlah kematian
    
    Args:
        sensor_history: List of dicts (4 terakhir / 2 jam), setiap dict punya:
                        temp, hum, ammo, Death
    
    Returns:
        {
            'predicted_death': int,
            'raw_prediction': float
        }
    """
    if forecasting_model is None:
        load_models()
    
    # Pastikan ada 4 data points (window 2 jam)
    n_steps_in = forecasting_config['n_steps_in']
    if len(sensor_history) < n_steps_in:
        raise ValueError(f"Need at least {n_steps_in} data points (2 hours), got {len(sensor_history)}")
    
    # Ambil 4 terakhir
    recent = sensor_history[-n_steps_in:]
    
    # Convert ke format yang dibutuhkan
    seq = []
    for point in recent:
        seq.append([
            point['temp'],
            point['hum'],
            point['ammo'],
            point['Death']  # Death value untuk learning pattern
        ])
    
    # Flatten
    X = np.array(seq).flatten()
    
    # Add statistical features
    X_stat = stats_features_single(X).reshape(1, -1)
    
    # Predict
    raw_pred = forecasting_model.predict(X_stat)[0]
    final_pred = int(round(max(0, raw_pred)))  # Tidak bisa negatif
    
    return {
        'predicted_death': final_pred,
        'raw_prediction': float(raw_pred)
    }
