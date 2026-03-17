# Use Python 3.12 slim image as base
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Create a non-privileged user for OpenShift
# UID 1001 is commonly used in OpenShift deployments
RUN groupadd -r appuser && useradd -r -u 1001 -g appuser appuser

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files for dependency installation
COPY pyproject.toml .
COPY src/ ./src/

# Install the project and its dependencies using uv
RUN uv pip install --system --no-cache .

# Copy the application entrypoint
COPY main.py .

# Create data directory for vector store
RUN mkdir -p /app/data && \
    chown -R appuser:appuser /app

# Switch to non-privileged user
USER appuser

# Expose port 8080 (OpenShift standard)
EXPOSE 8080

# Set environment variables
ENV PORT=8080
ENV PYTHONPATH=/app:/app/src

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
