FROM python:2.7

RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt1-dev \
    mediainfo

RUN pip install 2mp4
