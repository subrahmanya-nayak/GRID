FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=gridsite.settings \
    PYTHONPATH=/app/webapp

RUN apt-get update && apt-get install -y \
    bash \
    build-essential \
    curl \
    git \
    net-tools \
    lsof \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    python3.11-distutils \
    redis-server \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

WORKDIR /app

COPY requirements.txt ./
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY . ./

RUN curl -fsSL https://ollama.com/install.sh | sh
RUN bash -c "ollama serve & sleep 5 && ollama pull gemma2 && pkill ollama"

EXPOSE 8000

CMD bash -lc "redis-server --daemonize yes && \
    ollama serve & \
    sleep 5 && \
    ollama pull gemma2 && \
    python3 webapp/manage.py migrate && \
    celery -A gridsite worker --loglevel=info & \
    python3 webapp/manage.py runserver 0.0.0.0:8000"
