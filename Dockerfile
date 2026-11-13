FROM python:3.11-slim

WORKDIR /usr/src/app

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core fonts-noto-core fonts-noto-extra fonts-noto-color-emoji fontconfig libpango-1.0-0 libpangocairo-1.0-0 libcairo2 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# modele pour enlever le fond, telecharge a l'avance
ENV U2NET_HOME=/usr/src/app/.u2net
RUN python -c "from rembg import new_session; new_session('u2netp')"

COPY main.py ./
COPY stickerbot ./stickerbot

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/usr/src/app/stickerbot
CMD ["python", "main.py"]
