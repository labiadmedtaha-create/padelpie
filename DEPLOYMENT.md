# Déploiement en ligne — Padelpie

Cette version regroupe les deux espaces dans **un seul service web** :

- `/` → Padelpie
- `/clubs/` → Espace Clubs
- `/admin` → Dashboard Admin

La base SQLite et les photos sont stockées sous `/data`, prévu pour un disque persistant.

## Lancer avec Docker

1. Copier `.env.example` vers `.env`.
2. Remplacer `PADELPIE_SECRET_KEY` par une longue valeur aléatoire.
3. Exécuter `docker compose up -d --build`.
4. Ouvrir `http://localhost:8000`.

## Production

Utiliser un hébergeur qui fournit un disque persistant monté sur `/data`, puis placer un domaine et HTTPS devant le service.

Important : ne pas utiliser le serveur Flask de développement en production. Le conteneur utilise Gunicorn.
