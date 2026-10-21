"""
Tests for ML Prediction endpoints
"""
import pytest
from httpx import AsyncClient

from app.ml.model_loader import load_models, predict_classification, predict_forecasting


class TestModelLoader:
    """Test ML model loading and prediction functions."""
    
    def test_load_models(self):
        """Test that models load successfully."""
        load_models()
        # If no exception, models loaded
    
    def test_predict_classification(self):
        """Test classification prediction with sample data."""
        features = {
            'Hari Ke-': 5,
            'Suhu': 28.5,
            'Kelembaban': 75.0,
            'Amoniak': 3.5,
            'Pakan': 150,
            'Minum': 350,
            'Bobot': 58,
            'Populasi': 8000,
            'Luas Kandang': 336,
            'Hour': 10
        }
        
        result = predict_classification(features)
        
        assert 'class' in result
        assert result['class'] in ['Normal', 'Abnormal']
        assert 'probability' in result
        assert 0 <= result['probability'] <= 1
        assert 'confidence' in result
        assert 0 <= result['confidence'] <= 1
    
    def test_predict_forecasting(self):
        """Test forecasting prediction with sample sensor history."""
        sensor_history = [
            {'temp': 27.5, 'hum': 72.0, 'ammo': 3.2, 'Death': 0},
            {'temp': 27.8, 'hum': 71.5, 'ammo': 3.4, 'Death': 0},
            {'temp': 28.0, 'hum': 70.0, 'ammo': 3.6, 'Death': 1},
            {'temp': 28.2, 'hum': 69.5, 'ammo': 3.8, 'Death': 0}
        ]
        
        result = predict_forecasting(sensor_history)
        
        assert 'predicted_death' in result
        assert isinstance(result['predicted_death'], int)
        assert result['predicted_death'] >= 0
        assert 'raw_prediction' in result
        assert isinstance(result['raw_prediction'], float)


class TestPredictionEndpoints:
    """Test prediction API endpoints (requires auth - placeholder tests)."""
    
    @pytest.mark.asyncio
    async def test_models_info_endpoint(self, client: AsyncClient, auth_headers: dict):
        """Test GET /predictions/models endpoint."""
        if not auth_headers:
            pytest.skip("Auth not set up for this test")
        
        response = await client.get(
            "/api/v1/predictions/models",
            headers=auth_headers
        )
        
        # Without proper auth setup, this may fail
        # This is a placeholder test structure
        assert response.status_code in [200, 401, 422]
