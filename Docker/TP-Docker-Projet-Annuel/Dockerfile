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
    && rm -rf /var/lib/apt/lists/*

# Configuration de sudo pour tes utilisateurs
RUN echo "ALL ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Fausses commandes de gestion d'alimentation pour faire vrai
# Fausses commandes de gestion d'alimentation (via des fichiers signaux)
RUN echo '#!/bin/sh\necho "Arret du systeme demande..."\ntouch /tmp/shutdown.sig' > /usr/local/bin/shutdown && chmod +x /usr/local/bin/shutdown && \
    echo '#!/bin/sh\necho "Redemarrage du systeme..."\ntouch /tmp/reboot.sig' > /usr/local/bin/reboot && chmod +x /usr/local/bin/reboot && \
    cp /usr/local/bin/reboot /usr/local/bin/restart

# Script de demarrage intelligent avec boucle de surveillance des signaux d'arret
RUN echo '#!/bin/sh.real\napt-get update -qq >/dev/null 2>&1 &\nservice ssh start\nif [ $# -gt 0 ]; then exec "$@"; else while true; do if [ -f /tmp/shutdown.sig ]; then exit 0; fi; if [ -f /tmp/reboot.sig ]; then exit 1; fi; sleep 1; done; fi' > /usr/local/bin/startup.sh && chmod +x /usr/local/bin/startup.sh

RUN mkdir -p /var/run/sshd
RUN echo 'root:root' | chpasswd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Script de demarrage intelligent : met a jour le catalogue APT en arriere-plan sans bloquer le boot
RUN echo '#!/bin/sh.real\napt-get update -qq >/dev/null 2>&1 &\nservice ssh start\nif [ $# -gt 0 ]; then exec "$@"; else tail -f /dev/null; fi' > /usr/local/bin/startup.sh && chmod +x /usr/local/bin/startup.sh

# PIEGE INTELLIGENT (Verrouillage du shell)
RUN mv /bin/sh /bin/sh.real && \
    mv /bin/bash /bin/bash.real && \
    printf '#!/bin/sh.real\nif [ "$INTERNAL_LOGGED_IN" != "1" ] && [ $# -eq 0 ] && [ -t 0 ]; then\n  export OS_TYPE="Linux"\n  exec python3 /scripts/internal_login.py\nelse\n  exec /bin/sh.real "$@"\nfi\n' > /bin/sh && \
    printf '#!/bin/sh.real\nif [ "$INTERNAL_LOGGED_IN" != "1" ] && [ $# -eq 0 ] && [ -t 0 ]; then\n  export OS_TYPE="Linux"\n  exec python3 /scripts/internal_login.py\nelse\n  exec /bin/bash.real "$@"\nfi\n' > /bin/bash && \
    chmod +x /bin/sh /bin/bash

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 22 5000

# On utilise notre nouveau script de demarrage
ENTRYPOINT ["/usr/local/bin/startup.sh"]