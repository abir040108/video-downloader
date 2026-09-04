# language: Dockerfile, file: Dockerfile
# *pulls slim python, installs ffmpeg for yt-dlp muxing, starts uvicorn*
FROM python:3.9-slim

# Install ffmpeg for video/audio muxing
RUN apt-get update && apt-get install -y ffmpeg

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8000

# Start the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
