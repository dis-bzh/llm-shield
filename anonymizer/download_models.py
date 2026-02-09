import nltk
import ssl

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

def download_models():
    """Download NLTK models required for TextBlob and anonymization."""
    print("Downloading NLTK models...")
    
    models = [
        'brown',
        'punkt',
        'wordnet',
        'averaged_perceptron_tagger',
        'conll2000',
        'movie_reviews',
        'punkt_tab'  # Required for newer NLTK versions
    ]
    
    for model in models:
        print(f"Downloading {model}...")
        nltk.download(model, quiet=True)
        
    print("All models downloaded successfully.")

if __name__ == "__main__":
    download_models()
