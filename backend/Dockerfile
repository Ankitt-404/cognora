# Start from a small Python image
FROM python:3.12-slim

# All following commands run inside /srv in the container
WORKDIR /srv

# Install the small CPU-only PyTorch first (the embedding model needs it)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install the other packages (copied first so Docker can cache this step)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download the embedding model now, so the first request isn't slow
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

# Copy your code last, because it changes most often
COPY app ./app

# Start the API
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]