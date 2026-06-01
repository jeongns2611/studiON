FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy
ENV UV_CACHE_DIR=/tmp/uv-cache
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY . .
# 메인 AI 서버는 DSP 의존성만 설치하고, ML 추론은 외부 CLAP 서비스에 위임한다.
RUN uv sync --frozen --no-dev --group audio-dsp \
    && rm -rf /tmp/uv-cache

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
