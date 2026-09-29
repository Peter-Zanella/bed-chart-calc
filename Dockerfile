# Web app image: docker build -t jyotisa . && docker run -p 8000:8000 jyotisa
FROM python:3.12-slim
WORKDIR /app
COPY web/requirements.txt web/requirements.txt
# pyswisseph ships no wheel for this Python, so it compiles from source: needs gcc and g++
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ libc6-dev \
    && pip install --no-cache-dir -r web/requirements.txt \
    && apt-get purge -y gcc g++ libc6-dev && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
COPY . .
ENV PORT=8000
CMD ["sh", "-c", "uvicorn web.server:app --host 0.0.0.0 --port ${PORT}"]
