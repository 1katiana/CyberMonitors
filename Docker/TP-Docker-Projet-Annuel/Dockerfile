FROM python:3.9-slim

# Ajout de 'jq' pour lire le fichier JSON facilement
RUN apt-get update && apt-get install -y \
    sqlite3 \
    openssh-server \
    jq \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /var/run/sshd
RUN echo 'root:root' | chpasswd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# PIEGE INTELLIGENT : Intercepte les commandes bash/sh
RUN mv /bin/sh /bin/sh.real && \
    mv /bin/bash /bin/bash.real && \
    printf '#!/bin/sh.real\nif [ "$INTERNAL_LOGGED_IN" != "1" ] && [ $# -eq 0 ] && [ -t 0 ]; then\n  exec python3 /scripts/internal_login.py\nelse\n  exec /bin/sh.real "$@"\nfi\n' > /bin/sh && \
    printf '#!/bin/sh.real\nif [ "$INTERNAL_LOGGED_IN" != "1" ] && [ $# -eq 0 ] && [ -t 0 ]; then\n  exec python3 /scripts/internal_login.py\nelse\n  exec /bin/bash.real "$@"\nfi\n' > /bin/bash && \
    chmod +x /bin/sh /bin/bash

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 22 5000

# On lance l'initialisation dynamique avec le VRAI bash pour ne pas trigger le piege
ENTRYPOINT ["/bin/bash.real", "-c", "service ssh start && exec \"$@\"", "--"]