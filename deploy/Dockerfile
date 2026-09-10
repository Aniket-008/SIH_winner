# JAN-DRISHTI AI - image for horizontally scaled deployments
# The app is standard-library Python, so the image stays small and starts fast.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JAN_DRISHTI_HOST=0.0.0.0 \
    JAN_DRISHTI_PORT=8000 \
    JAN_DRISHTI_PROXY_LAYER=nginx

WORKDIR /app

# Only the application code is needed for the core (zero-dependency) runtime.
# Add requirements.txt here if you deploy the optional pandas/scikit-learn extras.
COPY jan_drishti ./jan_drishti
COPY website ./website
COPY data ./data
COPY scripts ./scripts

# Run as a non-root user
RUN useradd --create-home --shell /bin/bash jandrishti \
    && mkdir -p /app/data \
    && chown -R jandrishti:jandrishti /app
USER jandrishti

EXPOSE 8000

# Kubernetes/Docker health checks use the app's own probe, which reports
# concurrency, saturation and p95 latency so the balancer can make a real
# decision instead of a TCP handshake guess.
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import json,urllib.request; \
d=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2)); \
raise SystemExit(0 if d['status'] in ('ok','degraded') else 1)"

CMD ["python", "-m", "jan_drishti.server", "--host", "0.0.0.0", "--port", "8000"]
