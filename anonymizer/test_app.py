"""
Unit Tests for Anonymizer Service
"""
import pytest
from app import app, detect_secrets, anonymize_secrets


@pytest.fixture
def client():
    """Create test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    def test_health_returns_ok(self, client):
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json['status'] == 'healthy'


class TestAnonymizeEndpoint:
    """Tests for /anonymize endpoint."""
    
    def test_anonymize_email(self, client):
        response = client.post('/anonymize', json={
            'text': 'Contact me at john@example.com'
        })
        assert response.status_code == 200
        assert '{{EMAIL}}' in response.json['anonymized']
        assert 'john@example.com' not in response.json['anonymized']
    
    def test_anonymize_french_phone(self, client):
        response = client.post('/anonymize', json={
            'text': 'Appelez-moi au 0612345678'
        })
        assert response.status_code == 200
        assert '{{PHONE_FR}}' in response.json['anonymized']
        assert '0612345678' not in response.json['anonymized']
    
    def test_anonymize_openai_key(self, client):
        response = client.post('/anonymize', json={
            'text': 'My API key is sk-abc123xyz789012345678901234567890'
        })
        assert response.status_code == 200
        assert '{{OPENAI_KEY}}' in response.json['anonymized']
        assert 'sk-abc123' not in response.json['anonymized']
    
    def test_anonymize_multiple_pii(self, client):
        response = client.post('/anonymize', json={
            'text': 'Email: test@mail.com, Phone: 0698765432, Key: sk-test123456789012345678'
        })
        assert response.status_code == 200
        data = response.json
        assert data['pii_count'] >= 1
        assert data['secrets_count'] >= 1
    
    def test_anonymize_missing_text(self, client):
        response = client.post('/anonymize', json={})
        assert response.status_code == 400
        assert 'error' in response.json
    
    def test_anonymize_empty_text(self, client):
        response = client.post('/anonymize', json={'text': ''})
        assert response.status_code == 200
        assert response.json['anonymized'] == ''


class TestDetectSecrets:
    """Unit tests for detect_secrets function."""
    
    def test_detect_aws_key(self):
        text = 'AWS key: AKIAIOSFODNN7EXAMPLE'
        detections = detect_secrets(text)
        assert len(detections) >= 1
        assert any(d['type'] == 'aws_access_key' for d in detections)
    
    def test_detect_github_token(self):
        text = 'Token: ghp_1234567890abcdefghij1234567890abcdefgh'
        detections = detect_secrets(text)
        assert len(detections) >= 1
        assert any(d['type'] == 'github_token' for d in detections)
    
    def test_detect_jwt(self):
        text = 'JWT: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U'
        detections = detect_secrets(text)
        assert len(detections) >= 1
        assert any(d['type'] == 'jwt_token' for d in detections)
    
    def test_detect_no_secrets(self):
        text = 'This is a normal text without any secrets'
        detections = detect_secrets(text)
        assert len(detections) == 0


class TestAnonymizeSecrets:
    """Unit tests for anonymize_secrets function."""
    
    def test_anonymize_replaces_secrets(self):
        text = 'api_key=secret123456789012'
        result = anonymize_secrets(text)
        assert 'secret123456789012' not in result
        assert '{{API_KEY_GENERIC}}' in result
    
    def test_anonymize_preserves_normal_text(self):
        text = 'Hello, this is normal text'
        result = anonymize_secrets(text)
        assert result == text
