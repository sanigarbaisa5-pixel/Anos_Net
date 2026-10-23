# ANOS NET

Plateforme communautaire Free Fire construite avec Flask. Elle comprend :
- création de compte et connexion ;
- profils avec pseudo, ID Free Fire et rang ;
- chat public et messages privés ;
- équipes Battle Royale et Clash Squad ;
- classement d'activité ;
- espace administrateur pour modérer les messages et les membres.

## Lancer dans un environnement Python

```bash
python -m pip install -r requirements.txt
python server.py
```

Puis ouvrir `http://127.0.0.1:5000`.

## Déployer sur Render avec GitHub

1. Téléverser tous les fichiers et dossiers de ce projet dans un dépôt GitHub.
2. Sur Render, créer un **Web Service** connecté au dépôt.
3. Build command : `pip install -r requirements.txt`
4. Start command : `gunicorn server:app`
5. Ajouter ces variables d'environnement :
   - `SECRET_KEY` : une longue valeur aléatoire et privée ;
   - `ADMIN_USERNAME` : pseudo du compte administrateur initial ;
   - `ADMIN_PASSWORD` : mot de passe unique d'au moins 8 caractères ;
   - `DATABASE_URL` : URL de la base PostgreSQL fournie par Render.

Configure `ADMIN_USERNAME` et `ADMIN_PASSWORD` avant le premier démarrage si tu veux créer automatiquement un compte administrateur. Ne mets jamais les mots de passe ou clés secrètes dans le code ni dans GitHub.

Le chat utilise une actualisation périodique, pas des WebSockets. Le classement mesure l'activité sur ANOS NET et ne représente pas les statistiques officielles de Garena. Avant une ouverture publique, renforce la protection contre le spam, ajoute une protection CSRF, vérifie la configuration de production et prévois des sauvegardes de la base.
