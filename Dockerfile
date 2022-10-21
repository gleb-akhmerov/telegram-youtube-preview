FROM python:3.9-slim-bullseye
#FROM python:3.9-bullseye

WORKDIR /workdir

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
