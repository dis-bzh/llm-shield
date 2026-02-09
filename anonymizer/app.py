"""
Anonymizer Service - API Flask pour anonymiser les PII et secrets
Architecture: Tout est géré par Scrubadub (Détecteurs natifs + Détecteurs dynamiques depuis patterns.json)
"""
from flask import Flask, request, jsonify
import scrubadub
from scrubadub.detectors import RegexDetector, TextBlobNameDetector
from scrubadub.filth import Filth
import re
import json
import os
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configurer NLTK pour TextBlob
import nltk
if os.path.exists('/app/nltk_data'):
    nltk.data.path.append('/app/nltk_data')


# Chargeur de patterns
PATTERNS_FILE = os.getenv("PATTERNS_FILE", "patterns.json")
SENSITIVE_PATTERNS = {}

# Global scrubber instance
scrubber = None

def create_dynamic_detector(name, pattern):
    """Crée dynamiquement une classe Detector et Filth pour Scrubadub."""
    # 1. Créer une classe Filth spécifique (ex: 'ApiKeyFilth')
    # Le 'type' définira le placeholder {{TYPE}}
    filth_cls = type(
        f"{name.capitalize()}Filth",
        (Filth,),
        {'type': name}
    )
    
    # 2. Créer une classe Detector (ex: 'ApiKeyDetector')
    try:
        compiled_regex = re.compile(pattern)
    except re.error as e:
        logger.error(f"Invalid regex for {name}: {e}")
        return None

    detector_cls = type(
        f"{name.capitalize()}Detector",
        (RegexDetector,),
        {
            'name': name,
            'regex': compiled_regex,
            'filth_cls': filth_cls
        }
    )
    return detector_cls

def init_scrubber():
    """Initialise le scrubber avec les détecteurs par défaut + dynamiques."""
    global scrubber, SENSITIVE_PATTERNS
    
    # Nouveau scrubber propre
    new_scrubber = scrubadub.Scrubber()
    
    # Ajouter TextBlob pour les noms (si dispo)
    try:
        new_scrubber.add_detector(TextBlobNameDetector)
        logger.info("✅ Added TextBlobNameDetector")
    except Exception as e:
        logger.warning(f"⚠️ Could not add TextBlobNameDetector: {e}")

    # Charger patterns.json
    try:
        if os.path.exists(PATTERNS_FILE):
            with open(PATTERNS_FILE, 'r') as f:
                new_patterns = json.load(f)
            
            if isinstance(new_patterns, dict):
                SENSITIVE_PATTERNS = new_patterns
                count = 0
                for name, pattern in new_patterns.items():
                    # Check for collision with default detectors (e.g. 'email', 'url')
                    # We want our custom patterns to take precedence (overwrite)
                    try:
                        new_scrubber.remove_detector(name)
                        logger.info(f"ℹ️ Overwriting default detector: {name}")
                    except KeyError:
                        pass # Detector didn't exist, safe to add

                    detector_cls = create_dynamic_detector(name, pattern)
                    if detector_cls:
                        try:
                            new_scrubber.add_detector(detector_cls)
                            count += 1
                        except Exception as e:
                            logger.error(f"❌ Failed to add detector {name}: {e}")
                logger.info(f"✅ Loaded {count} dynamic patterns from {PATTERNS_FILE}")
            else:
                logger.error("patterns.json is not a dictionary")
    except Exception as e:
        logger.error(f"❌ Failed to load patterns: {e}")
        return False, str(e)

    scrubber = new_scrubber
    return True, "Scrubber initialized successfully"

# Initialisation au démarrage
init_scrubber()

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    detectors = list(scrubber._detectors.keys()) if scrubber else []
    return jsonify({
        "status": "healthy",
        "engine": "full-scrubadub",
        "detectors_count": len(detectors),
        "detectors": detectors
    })

@app.route('/management/reload', methods=['POST'])
def reload_patterns():
    """Recharge tout le scrubber."""
    success, msg = init_scrubber()
    if success:
        return jsonify({"status": "success", "message": msg, "detectors": list(scrubber._detectors.keys())})
    else:
        return jsonify({"status": "error", "message": msg}), 400

@app.route('/anonymize', methods=['POST'])
def anonymize():
    """Anonymise le texte via Scrubadub."""
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "Missing 'text' field"}), 400
    
    original_text = data['text']
    
    # Scrubbing
    try:
        anonymized_text = scrubber.clean(original_text)
        
        # Récupérer les détails (Filth)
        detections = []
        for filth in scrubber.iter_filth(original_text):
            detections.append({
                'type': filth.type, # Le type défini dans nos classes dynamiques ou natif (ex: 'name', 'email')
                'text': filth.text,
                'start': filth.beg,
                'end': filth.end,
                'detector': filth.detector_name
            })
            
    except Exception as e:
        logger.error(f"Scrubbing failed: {e}")
        return jsonify({"error": str(e)}), 500
    
    # Legacy counts for Gateway compatibility
    # Secrets = nos patterns custom (dans patterns.json)
    # PII = le reste (TextBlob, etc.)
    custom_detectors = set(SENSITIVE_PATTERNS.keys())
    secrets_count = sum(1 for d in detections if d['detector'] in custom_detectors)
    pii_count = len(detections) - secrets_count

    return jsonify({
        "anonymized": anonymized_text,
        "original_length": len(original_text),
        "anonymized_length": len(anonymized_text),
        "detections_count": len(detections),
        "detections": detections,
        "pii_count": pii_count,
        "secrets_count": secrets_count
    })


@app.route('/detect', methods=['POST'])
def detect():
    """Détecte sans remplacer."""
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "Missing 'text' field"}), 400
    
    text = data['text']
    detections = []
    
    try:
        for filth in scrubber.iter_filth(text):
            detections.append({
                'type': filth.type,
                'text': filth.text,
                'start': filth.beg,
                'end': filth.end,
                'detector': filth.detector_name
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    return jsonify({
        "detections": detections,
        "count": len(detections)
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
