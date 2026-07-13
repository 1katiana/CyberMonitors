FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    sqlite3 \
    openssh-server \
    sudo \
    iputils-ping \
    net-tools \
    iproute2 \
    curl \
    wget \
    nano \
    vim \
    htop \
    procps \
    tree \
    dnsutils \
    tcpdump \
    unzip \
    tar \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

RUN pip install bcrypt cryptography python-dotenv

# Configuration de sudo pour tes utilisateurs
RUN echo "ALL ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Fausses commandes de gestion d'alimentation
RUN echo '#!/bin/sh\nif [ "$(id -u)" != "0" ]; then echo "\033[91m[!] ACCES REFUSE : Privileges Administrateur requis.\033[0m"; exit 1; fi\necho "\033[93m[*] Arret du systeme en cours...\033[0m"\nnohup sh -c "sleep 1 && docker stop $(hostname)" > /dev/null 2>&1 &\nsleep 60' > /usr/local/bin/shutdown && chmod +x /usr/local/bin/shutdown && \
    echo '#!/bin/sh\nif [ "$(id -u)" != "0" ]; then echo "\033[91m[!] ACCES REFUSE : Privileges Administrateur requis.\033[0m"; exit 1; fi\necho "\033[93m[*] Redemarrage du systeme en cours...\033[0m"\nnohup sh -c "sleep 1 && docker restart $(hostname)" > /dev/null 2>&1 &\nsleep 60' > /usr/local/bin/reboot && chmod +x /usr/local/bin/reboot && \
    cp /usr/local/bin/reboot /usr/local/bin/restart

RUN mkdir -p /var/run/sshd
RUN echo 'root:root' | chpasswd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Script de demarrage intelligent : met a jour le catalogue APT en arriere-plan sans bloquer le boot
RUN echo '#!/bin/sh.real\napt-get update -qq >/dev/null 2>&1 &\nservice ssh start\nif [ $# -gt 0 ]; then exec "$@"; else tail -f /dev/null; fi' > /usr/local/bin/startup.sh && chmod +x /usr/local/bin/startup.sh
    
# PIEGE INTELLIGENT (Verrouillage du shell)
RUN mv /bin/sh /bin/sh.real && \
    mv /bin/bash /bin/bash.real && \
    printf '#!/bin/sh.real\nif [ "$INTERNAL_LOGGED_IN" != "1" ] && [ $# -eq 0 ] && [ -t 0 ]; then\n  if [ "$IS_MASTER_CONSOLE" = "1" ]; then\n    exec python3 /infrastructure/Docker/TP-Docker-Projet-Annuel/scripts/admin_console.py\n  else\n    export OS_TYPE="Linux"\n    exec python3 /scripts/internal_login.py\n  fi\nelse\n  exec /bin/sh.real "$@"\nfi\n' > /bin/sh && \
    printf '#!/bin/sh.real\nif [ "$INTERNAL_LOGGED_IN" != "1" ] && [ $# -eq 0 ] && [ -t 0 ]; then\n  if [ "$IS_MASTER_CONSOLE" = "1" ]; then\n    exec python3 /infrastructure/Docker/TP-Docker-Projet-Annuel/scripts/admin_console.py\n  else\n    export OS_TYPE="Linux"\n    exec python3 /scripts/internal_login.py\n  fi\nelse\n  exec /bin/bash.real "$@"\nfi\n' > /bin/bash && \
    chmod +x /bin/sh /bin/bash

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 22 5000

# On utilise notre nouveau script de demarrage
ENTRYPOINT ["/usr/local/bin/startup.sh"]