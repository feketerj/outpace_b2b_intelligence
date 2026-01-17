FROM python:3.11-slim

# Install curl for healthcheck and create non-root user
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code into backend subdirectory to match import structure
COPY . ./backend/

# Set PYTHONPATH so imports from backend.* work
ENV PYTHONPATH=/app

# Change ownership to non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Run uvicorn with multiple workers for production
# Workers = 2 * CPU cores + 1 (adjust via env var or override)
CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
