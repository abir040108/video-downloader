# language: Dockerfile, file: Dockerfile
# *bumped to python 3.11-slim to satisfy new yt-dlp master branch requirements*
FROM python:3.11-slim

# Install ffmpeg for video/audio muxing
RUN apt-get update && apt-get install -y ffmpeg

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8000

# Start the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
