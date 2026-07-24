FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY src ./src
COPY migrations ./migrations
COPY seeds ./seeds
COPY evals ./evals

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
