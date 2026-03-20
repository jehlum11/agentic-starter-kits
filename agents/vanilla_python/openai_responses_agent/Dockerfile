# OpenAI Responses Agent – OpenAI client + pure Python (Responses API, no agentic framework). Python 3.12+.
FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r appuser && useradd -r -u 1001 -g appuser appuser

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

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8080
ENV PORT=8080
ENV PYTHONPATH=/app:/app/src

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
