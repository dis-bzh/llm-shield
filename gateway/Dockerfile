# syntax=docker/dockerfile:1-labs
# =============================================================================
# LLM Shield - Gateway Service (Distroless Optimized)
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

# Copy and install requirements
WORKDIR /src
COPY requirements.txt .
RUN ["pip", "install", "--break-system-packages", "--no-cache-dir", "-r", "requirements.txt"]

# Stage 2: Production (nonroot, minimal)
FROM gcr.io/distroless/python3-debian${DEBIAN_VERSION}:nonroot

WORKDIR /app

# Copy gunicorn binary
COPY \
  --chmod=050 --chown=root:nonroot \
  --from=builder /usr/local/bin/gunicorn /usr/local/bin/gunicorn

# Copy site-packages without cache files
COPY \
  --chmod=a-rwx,g+rX --chown=root:nonroot \
  --exclude=**/__pycache__ \
  --exclude=**/*.pyc \
  --exclude=**/*.pyo \
  --from=builder /usr/local/lib/python3.11/dist-packages /usr/local/lib/python3.11/dist-packages

COPY --chmod=440 --chown=root:nonroot app.py ./

# Set PYTHONPATH for 3.11 (default in debian12 distroless)
ENV PYTHONPATH=/usr/local/lib/python3.11/dist-packages

COPY --chmod=440 --chown=root:nonroot healthcheck.py ./

EXPOSE 4000

ENTRYPOINT ["/usr/local/bin/gunicorn", "--bind", "0.0.0.0:4000", "--access-logfile", "-", "app:app"]
