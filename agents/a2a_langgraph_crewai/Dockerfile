# Single image for both A2A servers; pick role at deploy time via A2A_ROLE (crew | langgraph).
FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r appuser && useradd -r -u 1001 -g 0 -m -d /home/appuser appuser

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml .
COPY a2a_reply.py crew_a2a_server.py langgraph_a2a_server.py ./
RUN uv pip install --system --no-cache .

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# CrewAI runtime paths (OpenShift arbitrary UID / GID 0)
RUN mkdir -p /home/appuser/.local/share/app \
    && chown -R appuser:0 /app /home/appuser \
    && chmod -R g=u /app /home/appuser \
    && chmod g+x /app/entrypoint.sh

# Baked per image: crew vs langgraph (`docker build --build-arg A2A_ROLE=…`)
ARG A2A_ROLE=crew
ENV A2A_ROLE=${A2A_ROLE}
ENV HOME=/home/appuser
ENV PYTHONPATH=/app
ENV PORT=8080

USER appuser

EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
