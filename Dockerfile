FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir ".[web]"

VOLUME /data

ENV YABILABB_DATA_DIR=/data

EXPOSE 8000

CMD ["uvicorn", "yabilabb.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
