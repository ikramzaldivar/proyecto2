FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt

COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps -e .

COPY tests/ ./tests/
COPY quality.yaml ./quality.yaml

CMD ["pytest"]
