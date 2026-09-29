# Web app image: docker build -t jyotisa . && docker run -p 8000:8000 jyotisa
FROM python:3.12-slim
WORKDIR /app
COPY web/requirements.txt web/requirements.txt
RUN pip install --no-cache-dir -r web/requirements.txt
COPY . .
ENV PORT=8000
CMD ["sh", "-c", "uvicorn web.server:app --host 0.0.0.0 --port ${PORT}"]
