# syntax=docker/dockerfile:1-labs
# =============================================================================
# LLM Shield - Anonymizer Service (Distroless Optimized)
# =============================================================================
# Based on: https://piranna.github.io/2025/09/07/Minimal-and-secure-Python-distroless-Docker-images-with-Poetry/
# Security: No shell, nonroot user, minimal attack surface
# =============================================================================

ARG DEBIAN_VERSION=12
ARG PYTHON_VERSION=3.11

# Stage 1: Install pip and deps in distroless
FROM gcr.io/distroless/python3-debian${DEBIAN_VERSION} AS builder

# Install PIP
RUN ["python3", "-c", "from urllib.request import urlretrieve; urlretrieve('https://bootstrap.pypa.io/get-pip.py', 'get-pip.py')"]
RUN ["python3", "get-pip.py", "--break-system-packages"]

# Copy and install requirements (scrubadub + flask + gunicorn + textblob)
WORKDIR /src
COPY requirements.txt .
RUN ["pip", "install", "--break-system-packages", "--no-cache-dir", "-r", "requirements.txt"]
# Download textblob corpora AND missing nltk resources (punkt_tab)
RUN ["python3", "-m", "textblob.download_corpora"]
RUN ["python3", "-m", "nltk.downloader", "punkt_tab", "averaged_perceptron_tagger_eng"]

# Stage 2: Production (nonroot, minimal)
FROM gcr.io/distroless/python3-debian${DEBIAN_VERSION}:nonroot

WORKDIR /app

# Copy gunicorn binary
COPY \
  --chmod=050 --chown=root:nonroot \
  --from=builder /usr/local/bin/gunicorn /usr/local/bin/gunicorn

# Copy site-packages without cache files and tests
COPY \
  --chmod=a-rwx,g+rX --chown=root:nonroot \
  --exclude=**/__pycache__ \
  --exclude=**/*.pyc \
  --exclude=**/*.pyo \
  --exclude=**/tests \
  --exclude=**/test \
  --from=builder /usr/local/lib/python3.11/dist-packages /usr/local/lib/python3.11/dist-packages

COPY --chmod=440 --chown=root:nonroot app.py ./

# Copy NLTK data for TextBlob/Scrubadub
COPY --chown=nonroot:nonroot --from=builder /root/nltk_data /app/nltk_data
ENV NLTK_DATA=/app/nltk_data

COPY --chmod=440 --chown=root:nonroot healthcheck.py ./

EXPOSE 5001

ENTRYPOINT ["/usr/local/bin/gunicorn", "--bind", "0.0.0.0:5001", "app:app"]
