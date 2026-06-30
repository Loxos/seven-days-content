# Tiny, dependency-free engine image. git is needed at runtime to clone/push the
# content branch; ca-certificates for HTTPS to the LLM provider and GitHub.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

# Non-root. The content working tree lives on a writable emptyDir at runtime.
RUN useradd -m -u 10001 artist
USER artist

ENTRYPOINT ["python", "-m", "sevendays"]
