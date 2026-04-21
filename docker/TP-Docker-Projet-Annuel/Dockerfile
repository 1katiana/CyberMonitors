FROM python:3.9-slim

# 1. Installation des paquets systeme (SQLite et le serveur SSH)
RUN apt-get update && apt-get install -y \
    sqlite3 \
    openssh-server \
    && rm -rf /var/lib/apt/lists/*

# 2. Configuration requise pour le serveur SSH
RUN mkdir -p /var/run/sshd
RUN echo 'root:root' | chpasswd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# 3. Creation des comptes utilisateurs de simulation
RUN useradd -m -s /bin/bash Arnaud && echo "Arnaud:CyberMonitor2026!" | chpasswd
RUN useradd -m -s /bin/bash Katiana && echo "Katiana:CyberMonitor2026!" | chpasswd
RUN useradd -m -s /bin/bash Test && echo "Test:Test!" | chpasswd

# 4. Configuration de l'environnement Python
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# 5. Ouverture des ports reseau
EXPOSE 22 5000

# 6. Astuce : Lancement de SSH en fond, puis execution de la commande de ton docker compose
ENTRYPOINT ["/bin/sh", "-c", "service ssh start && exec \"$@\"", "--"]