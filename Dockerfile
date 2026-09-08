# Weekly Review Pulse — backend API only (Railway)
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    BACKEND_ONLY=1

COPY requirements-app.txt .
RUN pip install --no-cache-dir -r requirements-app.txt

COPY config.yaml .
COPY .env.example .
COPY src ./src
COPY data ./data

EXPOSE 8080

# Railway injects PORT. Use src.web so slim requirements-app.txt is enough
# (python -m src would import the LangChain pipeline at module load).
CMD ["python", "-m", "src.web", "--backend-only"]
