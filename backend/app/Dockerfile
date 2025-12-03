FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Set PYTHONPATH to /backend so that 'from app.xxx' imports work correctly
ENV PYTHONPATH=/backend

WORKDIR /backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

# Copy requirements from app directory
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire app directory to /backend/app
COPY app /backend/app

# Create necessary directories
RUN mkdir -p /backend/logs /backend/app/static/uploads

EXPOSE 8000

# Run the application from the app directory
CMD ["python", "/backend/app/main.py"]
