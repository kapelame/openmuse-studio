FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-noto-cjk fonts-inter && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY apps ./apps
COPY cli ./cli
COPY packages ./packages
RUN pip install --no-cache-dir uv && uv sync --no-dev
COPY .env.example .env.example
CMD ["uv", "run", "uvicorn", "openmuse_api.main:app", "--app-dir", "apps/api", "--host", "0.0.0.0", "--port", "8000"]
