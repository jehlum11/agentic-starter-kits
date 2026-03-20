# Use Python 3.12 slim image as base
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Create a non-privileged user for OpenShift
# UID 1001 is commonly used in OpenShift deployments
# Adding to root group (GID 0) is the OpenShift convention for arbitrary UIDs
RUN groupadd -r appuser && useradd -r -u 1001 -g 0 -m -d /home/appuser appuser

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files for dependency installation
COPY pyproject.toml .
COPY src/ ./src/

# Install the project and its dependencies using uv
RUN uv pip install --system --no-cache .

# Copy the application entrypoint, playground UI, and images
COPY main.py .
COPY playground/ ./playground/
COPY images/ ./images/

# Pre-create the directory that CrewAI writes to at import time
# (crewai.utilities.paths.db_storage_path -> ~/.local/share/app/)
# Make everything group-writable (GID 0) for OpenShift arbitrary UID support
RUN mkdir -p /home/appuser/.local/share/app \
    && chown -R appuser:0 /app /home/appuser \
    && chmod -R g=u /app /home/appuser

# Switch to non-privileged user
USER appuser

# Expose port 8080 (OpenShift standard)
EXPOSE 8080

# Set environment variables
ENV PORT=8080
ENV HOME=/home/appuser
ENV PYTHONPATH=/app:/app/src

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
