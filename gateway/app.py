"""
Gateway Service - Proxy OpenAI-compatible qui anonymise avant d'envoyer au LLM
Architecture: Client → Gateway → Anonymizer → LiteLLM → LLM externe

SÉCURITÉ: Mode fail-safe - si l'anonymisation échoue, la requête est BLOQUÉE
"""
import logging
import os
import requests
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

# Configuration des services
ANONYMIZER_URL = os.getenv("ANONYMIZER_URL", "http://anonymizer:5001")
LITELLM_URL = os.getenv("LITELLM_URL", "http://litellm:4000")

# Configure logging pour voir clairement l'anonymisation
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AnonymizationError(Exception):
    """Exception levée quand l'anonymisation échoue."""
    pass


def anonymize_text(text: str) -> str:
    """
    Envoie le texte à l'anonymizer et retourne la version anonymisée.
    FAIL-SAFE: Si l'anonymisation échoue, une exception est levée (pas de fallback).
    """
    try:
        response = requests.post(
            f"{ANONYMIZER_URL}/anonymize",
            json={"text": text},
            timeout=10
        )
        if response.status_code == 200:
            result = response.json()
            logger.info(f"🔒 Anonymisé ({result['anonymized_length']} chars): {result['anonymized'][:200]}...")
            logger.info(f"   → PII détectés: {result['pii_count']}, Secrets: {result['secrets_count']}")
            return result["anonymized"]
        else:
            logger.error(f"❌ Anonymizer HTTP error: {response.status_code}")
            raise AnonymizationError(f"Anonymizer returned {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Anonymizer connection error: {e}")
        raise AnonymizationError(f"Cannot reach anonymizer: {e}")


def anonymize_messages(messages: list) -> list:
    """
    Anonymise tous les messages de la conversation.
    FAIL-SAFE: Si un message ne peut pas être anonymisé, une exception est levée.
    """
    anonymized = []
    for i, msg in enumerate(messages):
        content = msg.get("content", "")
        if isinstance(content, str) and content:
            try:
                anonymized_content = anonymize_text(content)
                anonymized.append({**msg, "content": anonymized_content})
            except AnonymizationError as e:
                logger.error(f"❌ Failed to anonymize message {i}: {e}")
                raise
        else:
            # Message vide ou format non-string (multi-modal)
            anonymized.append(msg)
    return anonymized


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    # Vérifie aussi que l'anonymizer est accessible
    try:
        resp = requests.get(f"{ANONYMIZER_URL}/health", timeout=5)
        anonymizer_ok = resp.status_code == 200
    except Exception:
        anonymizer_ok = False

    status = "healthy" if anonymizer_ok else "degraded"
    return jsonify({
        "status": status,
        "service": "gateway",
        "anonymizer": "ok" if anonymizer_ok else "unreachable"
    })


@app.route('/v1/models', methods=['GET'])
def list_models():
    """Proxy la liste des modèles depuis LiteLLM."""
    try:
        response = requests.get(f"{LITELLM_URL}/v1/models", timeout=10)
        return Response(
            response.content,
            status=response.status_code,
            content_type=response.headers.get('content-type')
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    """
    Endpoint principal compatible OpenAI.
    1. Reçoit la requête
    2. Anonymise les messages (OBLIGATOIRE)
    3. Forward à LiteLLM
    4. Retourne la réponse

    SÉCURITÉ: Si l'anonymisation échoue, la requête est BLOQUÉE (503).
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "No JSON data"}), 400

    logger.info("=" * 60)
    logger.info("🚀 Nouvelle requête chat/completions")
    logger.info(f"   Modèle: {data.get('model', 'unknown')}")

    # Anonymiser les messages (OBLIGATOIRE - fail-safe)
    if "messages" in data:
        try:
            original_messages = data["messages"]
            anonymized_messages = anonymize_messages(original_messages)
            data["messages"] = anonymized_messages
        except AnonymizationError as e:
            logger.error(f"🚫 REQUÊTE BLOQUÉE - Anonymisation échouée: {e}")
            return jsonify({
                "error": "Anonymization failed - request blocked for security",
                "detail": str(e)
            }), 503

    logger.info("📤 Envoi à LiteLLM...")

    # Forward à LiteLLM
    try:
        response = requests.post(
            f"{LITELLM_URL}/v1/chat/completions",
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=60
        )

        logger.info(f"📥 Réponse LiteLLM: {response.status_code}")
        logger.info("=" * 60)

        return Response(
            response.content,
            status=response.status_code,
            content_type=response.headers.get('content-type')
        )
    except Exception as e:
        logger.error(f"LiteLLM error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logger.info("🌐 Gateway démarré - Port 4000")
    logger.info(f"   Anonymizer: {ANONYMIZER_URL}")
    logger.info(f"   LiteLLM: {LITELLM_URL}")
    logger.info("🔒 Mode FAIL-SAFE activé: requêtes bloquées si anonymisation échoue")
    app.run(host='0.0.0.0', port=4000, debug=True)
