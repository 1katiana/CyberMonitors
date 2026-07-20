Bienvenue sur la documentation détaillée du projet CyberMonitors.

Ce fichier read me a été rédigé pour vous accompagner pas à pas dans la compréhension, le déploiement et l'utilisation de notre infrastructure de supervision de sécurité.

# CyberMonitors - Projet Annuel de Sécurité Informatique

Ce projet représente notre travail de fin d'année pour le Bachelor en Sécurité Informatique à l'ESGI, au sein du Campus Eductive d'Aix-en-Provence. Il correspond à l'année universitaire 2025-2026.

# Crédits du projet : Développé et conçu par Arnaud Martinez et Katiana Aoudia.

# Avertissement Système

Ce projet a été intégralement pensé et développé pour fonctionner de manière optimale sur un environnement Windows. Il n'a pas été testé sur les systèmes d'exploitation macOS ou sur les distributions Linux. Son comportement sur ces plateformes n'est donc pas garanti.

# Fonctionnement Global et Catégories de Scripts

Pour rendre l'infrastructure compréhensible, voici comment nous avons divisé notre système. Aucun de ces scripts ne nécessite d'être lancé manuellement, tout est automatisé et orchestré par Docker.

- Le Parc Informatique (Simulation) : Nous avons créé un réseau de machines virtuelles vulnérables qui composent l'entreprise fictive. Ce parc inclut des serveurs Linux (linux-srv-1, linux-srv-2) et des postes Windows (win-wkst-1, win-wkst-2, win-srv-indispensable). Un script résident simule en permanence l'activité des utilisateurs, la consommation des ressources (CPU, RAM, Disque, Température), mais simule également de véritables attaques comme des ransomwares, des mineurs de cryptomonnaie ou des attaques DDoS.

- Le Centre de Contrôle (Administration) : Ce sont les scripts centraux de gestion. Ils permettent d'initialiser l'infrastructure de manière sécurisée, de gérer la base de données, et d'offrir une console d'administration puissante pour répondre aux incidents.

- L'Interface Web SOC (Visualisation) : Un site web local développé en thon (Flask) qui tourne en arrière-plan. Il récupère la télémétrie des machines pour générer des graphiques de surveillance en temps réel et remonte les alertes critiques.
 
# Guide de Déploiement Étape par Étape

La mise en place a été rendue la plus fluide et accueillante possible. Veuillez suivre l'ordre exact de ces commandes.

1. Préparation du dossier de configuration

Ouvrez votre terminal (PowerShell ou Invite de commandes) et rendez-vous dans le dossier racine du projet :


''cd CyberMonitors\Docker\TP-Docker-Projet-Annuel''

Dans ce dossier précis, vous devez créer un fichier totalement vide nommé .env. Ce fichier est crucial : le système ira automatiquement le remplir pour vous avec les configurations sensibles lors de l'initialisation.

2. Démarrage de l'infrastructure Docker

Une fois votre fichier .env créé, lancez l'environnement avec Docker Compose en utilisant la commande suivante :

- docker compose up -d --build

L'infrastructure va se mettre en place. Les machines du parc seront mises en attente de manière sécurisée jusqu'à ce que la configuration initiale soit finalisée.

3. Entrée dans le conteneur principal

Vous n'avez pas besoin de lancer des scripts thon de votre côté. Tout se passe à l'intérieur du conteneur de gestion sécurisé. Pour y entrer, tapez simplement :

- docker exec -it monitor_dashboard bash

(C'est ici que réside la commande principale pour contrôler tout votre parc informatique).

# Le Processus d'Initialisation Automatique

Dès que vous entrez dans le conteneur monitor_dashboard, le système détecte qu'il s'agit d'un premier démarrage et lance automatiquement le script d'initialisation. Vous n'avez qu'à suivre les indications à l'écran.

Le script d'initialisation est la clé de voûte de la sécurité du projet. Voici ce qu'il va vous demander et accomplir de manière autonome :

- Configuration des Alertes : Il va vous demander une adresse e-mail (Gmail, Microsoft ou autre). Pour s'assurer que vous recevrez bien les alertes en cas de crise, le script vous enverra instantanément un code de vérification à 6 chiffres par e-mail qu'il faudra renseigner.

- Génération des Clés : Il va créer ou configurer les clés de chiffrement de haut niveau (Fernet) pour protéger la base de données et les sauvegardes.
 
- Création du Compte Maître : Il va vous guider pour créer le profil de l'Administrateur principal (Master), avec des règles de mot de passe strictes.
 
Une fois cette procédure terminée avec succès, le script d'initialisation laisse sa place automatiquement et sans aucune coupure à la Console d'Administration Centrale.

# La Console d'Administration

La console d'administration est votre outil de réponse à incident (Incident Response). Une fois authentifié sur cette interface dans votre terminal, vous aurez le contrôle absolu sur le parc simulé :

- Allumer, éteindre ou relancer les conteneurs du parc informatique.
 
- Déclencher volontairement des attaques (Ransomware, DDoS, etc.) sur les machines pour tester vos défenses.
 
- Isoler des machines compromises du réseau (mise en quarantaine) sans les éteindre, ce qui permet de bloquer l'infection tout en gardant une connexion pour l'investigation numérique.
 
- Créer, modifier ou bannir d'autres utilisateurs du système.
 
- Gérer les sauvegardes chiffrées de l'infrastructure et restaurer le système en cas de corruption grave.
 
# Le Site Web (Tableau de Bord SOC)

En plus de la console dans le terminal, une interface graphique complète est à votre disposition dans votre navigateur web.

- Accès : Rendez-vous sur http://localhost:8050 depuis votre navigateur.

- Vos Comptes et la Sécurité : L'accès nécessite d'être connecté. Le site intègre un système de sessions sécurisées qui vous déconnecte automatiquement après 15 minutes d'inactivité. Vous pouvez également gérer vos informations de profil directement depuis cette interface web et crée des comptes.
 
- Monitoring et Gestion : Le tableau de bord affiche des graphiques précis sur l'état de santé de chaque conteneur (Utilisation CPU, Mémoire RAM, Espace Disque, Températures). C'est également par ce site que vous pouvez consulter les journaux de logs détaillés de l'infrastructure, superviser l'état des conteneurs, et être averti via un système de notifications visuelles rouges lors d'alertes de sécurité critiques.
 
