FROM python:3.12-slim

WORKDIR /app

# Install dependencies before copying application code so this layer is cached.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source (respects .dockerignore).
COPY . .

# Create the output directory and a non-root user, then hand over ownership.
RUN mkdir -p /app/output \
    && addgroup --system appuser \
    && adduser --system --ingroup appuser --home /home/appuser appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
