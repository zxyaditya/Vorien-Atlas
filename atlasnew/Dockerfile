FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc g++ curl && rm -rf /var/lib/apt/lists/*

# Install python dependencies from requirements.txt
COPY requirements.txt /app/
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . /app/

# Set Python Path
ENV PYTHONPATH=/app/libs/python:/app

CMD ["uvicorn", "apps.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
