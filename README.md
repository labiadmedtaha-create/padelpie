# Padelpie — Version finale MVP

## Deux sites connectés
- **Padelpie joueurs** : `http://127.0.0.1:5000`
- **Padelpie Clubs / gérants** : `http://127.0.0.1:5001`
- Les deux sites partagent la même base centrale `data/padelpie.db`.

## Lancement Windows
1. Double-cliquer `LANCER_PADELPIE.bat`.
2. Dans une deuxième fenêtre, double-cliquer `LANCER_ESPACE_CLUBS.bat`.
3. Ouvrir les deux adresses ci-dessus.

## Compte test joueur
- Email : `test@padelpie.ma`
- Mot de passe : `PadelpieTest123`
- Ce compte est un joueur normal, sans accès admin.

## Administrateur
Sur le site joueurs, connecter :
- Email : `medtahalabiad@gmail.com`
- Mot de passe : `Tahalabiad2`

Cette connexion ouvre automatiquement le dashboard Admin.

## Espace gérant
Sur `http://127.0.0.1:5001`, un gérant peut créer son compte puis :
- ajouter son club ;
- renseigner ville, zone, adresse, téléphone, horaires, tarif et description ;
- définir le nombre de terrains et leur type ;
- bloquer un créneau pour un terrain ou tous les terrains ;
- consulter les réservations reçues via Padelpie.

Les clubs ajoutés sont immédiatement disponibles dans BOOK du site joueurs.

## Profil joueur
Le joueur peut ajouter une photo JPG, PNG ou WEBP depuis son profil.

## Important
La version finale ne précharge aucun terrain de démonstration. Les clubs sont ajoutés par les gérants ou par une future interface d'administration.
