"""
Unit Tests for Gateway Service
"""
import pytest
from unittest.mock import patch, Mock
from app import app, AnonymizationError


@pytest.fixture
def client():
    """Create test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    @patch('app.requests.get')
    def test_health_with_anonymizer_ok(self, mock_get, client):
        mock_get.return_value = Mock(status_code=200)
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json['status'] == 'healthy'
        assert response.json['anonymizer'] == 'ok'
    
    @patch('app.requests.get')
    def test_health_with_anonymizer_down(self, mock_get, client):
        mock_get.side_effect = Exception('Connection refused')
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json['status'] == 'degraded'
        assert response.json['anonymizer'] == 'unreachable'


class TestChatCompletions:
    """Tests for /v1/chat/completions endpoint."""
    
    @patch('app.requests.post')
    def test_chat_with_successful_anonymization(self, mock_post, client):
        # Mock anonymizer response
        anonymizer_response = Mock()
        anonymizer_response.status_code = 200
        anonymizer_response.json.return_value = {
            'anonymized': 'My email is {{EMAIL}}',
            'anonymized_length': 21,
            'pii_count': 1,
            'secrets_count': 0
        }
        
        # Mock LiteLLM response
        litellm_response = Mock()
        litellm_response.status_code = 200
        litellm_response.content = b'{"choices": [{"message": {"content": "Hello!"}}]}'
        litellm_response.headers = {'content-type': 'application/json'}
        
        mock_post.side_effect = [anonymizer_response, litellm_response]
        
        response = client.post('/v1/chat/completions', json={
            'model': 'gpt-3.5-turbo',
            'messages': [{'role': 'user', 'content': 'My email is test@example.com'}]
        })
        
        assert response.status_code == 200
    
    @patch('app.requests.post')
    def test_chat_blocks_when_anonymizer_fails(self, mock_post, client):
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError('Anonymizer unavailable')
        
        response = client.post('/v1/chat/completions', json={
            'model': 'gpt-3.5-turbo',
            'messages': [{'role': 'user', 'content': 'Test message'}]
        })
        
        assert response.status_code == 503
        assert 'blocked' in response.json['error'].lower()
    
    @patch('app.requests.post')
    def test_chat_blocks_when_anonymizer_returns_error(self, mock_post, client):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response
        
        response = client.post('/v1/chat/completions', json={
            'model': 'gpt-3.5-turbo',
            'messages': [{'role': 'user', 'content': 'Test message'}]
        })
        
        assert response.status_code == 503
    
    def test_chat_missing_json(self, client):
        response = client.post('/v1/chat/completions', 
                               data='not json',
                               content_type='application/json')
        assert response.status_code == 400


class TestFailSafe:
    """Tests for fail-safe security behavior."""
    
    @patch('app.requests.post')
    def test_no_data_leakage_on_anonymizer_timeout(self, mock_post, client):
        """Verify that original data is NEVER sent if anonymization fails."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout('Timeout')
        
        sensitive_data = 'My password is super_secret_123'
        response = client.post('/v1/chat/completions', json={
            'model': 'gpt-3.5-turbo',
            'messages': [{'role': 'user', 'content': sensitive_data}]
        })
        
        # Must block the request
        assert response.status_code == 503
        
        # Verify LiteLLM was never called (only 1 call to anonymizer, not 2)
        assert mock_post.call_count == 1
