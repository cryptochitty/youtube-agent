FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libfreetype6 \
    libfreetype6-dev \
    fonts-dejavu-core \
    fonts-liberation \
    fonts-freefont-ttf \
    fontconfig \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p outputs/scripts outputs/audio outputs/images outputs/videos \
             outputs/thumbnails outputs/metadata outputs/jobs

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
