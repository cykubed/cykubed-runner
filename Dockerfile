FROM python:3.11.0-alpine

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt  --no-cache-dir --disable-pip-version-check -q

COPY ./src/ /app
ENTRYPOINT python main.py
