# Use Ubuntu base
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    bash \
    python3.11 \
    python3.11-venv \
    python3.11-distutils \
    lsof \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Set python3 and pip3 to point to python3.11
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

# Install Python packages
COPY requirements.txt /tmp/requirements.txt
RUN python3.11 -m pip install --no-cache-dir -r /tmp/requirements.txt

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Pre-pull the Gemma 2 model so it’s ready
RUN bash -c "ollama serve & sleep 5 && ollama pull gemma2 && pkill ollama"

# Set working directory
WORKDIR /app

# Optional: copy your scripts into the container
# COPY . /app/

# Start Ollama in background and keep shell open
CMD bash -c "ollama serve & sleep 5 && ollama pull gemma2 && exec bash"

