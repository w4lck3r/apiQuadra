# API de Traitement de Fichiers QuadraCompta

Une API REST basée sur Flask pour le traitement et la préparation des fichiers de données financières pour QuadraCompta (Facture/Avoir). Le service traite les enregistrements financiers, les regroupe par numéros de compte et gère la consolidation automatique des fichiers ainsi que les transferts SFTP.

## Fonctionnalités

- Traitement et regroupement des enregistrements financiers par numéros de compte
- Consolidation automatique des résultats tous les vendredis à 19h00 GMT
- Intégration SFTP pour les transferts sécurisés
- Documentation Swagger interactive
- Planification des tâches en arrière-plan
- Suivi de l'historique des traitements

## Prérequis

- Python 3.8+
- Accès au serveur SFTP

## Installation

1. Clonez le dépôt et naviguez vers le répertoire du projet

2. Créez et activez un environnement virtuel :
```bash
python -m venv venv
source venv/bin/activate  # Sur Windows : venv\Scripts\activate
```

3. Installez les packages requis :
```bash
pip install flask flasgger pysftp APScheduler
```

## Structure du Projet

```
├── uploads/           # Stockage temporaire des fichiers téléchargés
├── results/          # Stockage des résultats traités
├── script.py         # Fichier principal de l'application
└── processed_files.txt # Fichier de suivi des entrées traitées
```

## Configuration

L'application utilise la configuration par défaut suivante :

```python
UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
SFTP_HOST = 'localhost'
SFTP_USERNAME = 'user'
SFTP_PASSWORD = 'password'
SFTP_REMOTE_PATH = '/pub/main_results.txt'
```

Mettez à jour ces valeurs dans `script.py` selon votre environnement.

## Points d'Accès API

### POST /process
Traite un fichier financier unique et renvoie immédiatement les résultats.

**Requête :**
- Méthode : POST
- Content-Type : multipart/form-data
- Corps : fichier (Facture/Avoir)

**Réponse :**
- 200 : Fichier traité
- 400 : Message d'erreur si le fichier est manquant ou vide

### POST /append_results
Traite un fichier et ajoute les résultats au fichier de consolidation principal.

**Requête :**
- Méthode : POST
- Content-Type : multipart/form-data
- Corps : fichier (Facture/Avoir)

**Réponse :**
- 200 : Message de confirmation
- 400 : Message d'erreur si le fichier est manquant ou vide

## Format de Fichier

### Structure d'Entrée
```
M[numéro_compte(8)][code_journal(2)]...[montant(13)]...  # Transaction principale
I[pourcentage_distribution(5)][montant(13)][code_centre(3)]... # Distribution
```

### Traitement
- Regroupe les transactions par numéros de compte
- Maintient l'ordre original des lignes M
- Consolide les lignes I associées

## Tâches Automatisées

- **Planification des sauvegardes** : Tous les vendredis à 19h00 GMT
- **Processus** : 
  1. Sauvegarde du fichier main_results.txt actuel
  2. Efface le fichier pour la semaine suivante
  3. Télécharge vers le serveur SFTP

## Documentation

Accédez à la documentation API interactive à :
```
http://localhost:5000/docs
```

## Exécution de l'Application

1. Démarrez le serveur :
```bash
python script.py
```

2. L'application s'exécutera sur `http://localhost:5000`

## Tests

### Test de la route /process
```bash
curl -X POST -F "file=@chemin_vers_votre_fichier.txt" http://127.0.0.1:5000/process -o fichier_resultat.txt
```

### Test de la route /append_results
```bash
curl -X POST -F "file=@chemin_vers_fichier_traite.txt" http://127.0.0.1:5000/append_results
```

## Gestion des Erreurs

L'application gère :
- Fichiers manquants ou vides
- Problèmes de connexion SFTP
- Erreurs de traitement de fichiers
- Conversions de montants invalides

## Notes de Sécurité

- La vérification des clés hôtes SFTP est désactivée pour les tests
- Mettez à jour les identifiants SFTP avant le déploiement
- Le mode debug est activé par défaut

## Support

Pour les problèmes et les demandes de fonctionnalités, veuillez créer une issue dans le dépôt.