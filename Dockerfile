FROM python:3.11-slim

# fonts-dejavu-core нужен, чтобы PDF корректно печатал русский текст
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

# data volume for sqlite + invoices
RUN mkdir -p /app/data/invoices

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "app.main"]
