FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app/src

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir ".[prod]"

COPY dbt ./dbt
COPY deploy/run_daily.sh ./run_daily.sh
RUN chmod +x run_daily.sh

# Runs as a non-root user; credentials come from the job's service account
RUN useradd --create-home pipeline
USER pipeline

ENV WAREHOUSE=bigquery
ENTRYPOINT ["./run_daily.sh"]
