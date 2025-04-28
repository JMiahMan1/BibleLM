# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies required by libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    tesseract-ocr \
    tesseract-ocr-eng \
    # Add other language packs if needed, e.g., tesseract-ocr-fra
    libgl1-mesa-glx \
    libglib2.0-0 \
    # Dependencies for Coqui TTS (if using and installing via pip)
    # espeak-ng \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Copy only requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend application code
COPY . .

# Make sure data directories exist and have correct permissions if needed
# (Directories are created by config loader, but this ensures base exists)
# The volume mount will overlay this later.
RUN mkdir -p /app/data/uploads /app/data/processed /app/data/audio_exports /app/data/db

# Expose the port the app runs on
EXPOSE 8000

# Define the command to run the application
# Use Gunicorn for production later, Uvicorn for development/simplicity here
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Optional: Add healthcheck
# HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
#   CMD curl -f http://localhost:8000/ || exit 1 # Needs a simple healthcheck endpoint in main.py
