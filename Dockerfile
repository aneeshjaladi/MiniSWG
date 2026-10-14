# Dockerfile for MiniSWG (Mini Secure Web Gateway)
FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy configuration and code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY miniswg/ ./miniswg/
COPY config/ ./config/

# Create logs directory
RUN mkdir -p logs

# Expose proxy port (8080) and admin web interface
EXPOSE 8080

# Run MiniSWG proxy listening on all interfaces (0.0.0.0)
CMD ["python", "-m", "miniswg.proxy", "--host", "0.0.0.0", "--port", "8080", "--policy", "config/policy.json"]
