# Anonymizer Service

Python microservice using Scrubadub and custom regex patterns to anonymize sensitive data (PII, secrets) before sending to LLMs.

## Features

- **PII Detection**: Emails, names, phone numbers (including French format)
- **Secret Detection**: API keys (OpenAI, Anthropic, AWS, GitHub tokens)
- **Fail-Safe**: Returns error if anonymization fails (no data leakage)
- **Lightweight**: Multi-stage Docker build (~50MB image)

## API

### Health Check
```bash
curl http://localhost:5001/health
```

### Anonymize Text
```bash
curl -X POST http://localhost:5001/anonymize \
  -H "Content-Type: application/json" \
  -d '{"text": "Contact john@example.com or call 0612345678"}'
```

**Response:**
```json
{
  "anonymized": "Contact {{EMAIL}} or call {{PHONE_FR}}",
  "original_length": 47,
  "anonymized_length": 38,
  "pii_count": 1,
  "secrets_count": 1
}
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python app.py

# Run tests
pytest
```

## Docker

```bash
# Build
docker build -t llm-shield-anonymizer .

# Run
docker run -p 5001:5001 llm-shield-anonymizer
```

## Patterns Detected

| Type | Pattern | Placeholder |
|------|---------|-------------|
| Email | `*@*.com` | `{{EMAIL}}` |
| French Phone | `06/07...` | `{{PHONE_FR}}` |
| OpenAI Key | `sk-...` | `{{OPENAI_KEY}}` |
| Generic API Key | `api_key=...` | `{{API_KEY_GENERIC}}` |
| AWS Access Key | `AKIA...` | `{{AWS_ACCESS_KEY}}` |
| GitHub Token | `ghp_...` | `{{GITHUB_TOKEN}}` |
