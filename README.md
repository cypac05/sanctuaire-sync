🌱 Sanctuaire Sync

Synchronisation automatique Directus vers Zenodo (Sandbox & Production)

Sanctuaire Sync est une application web légère basée sur FastAPI et Vue.js qui permet de synchroniser automatiquement le contenu de vos collections Directus vers des dépôts Zenodo.
✨ Fonctionnalités Clés

    Synchronisation Multi-Tables : Traitez plusieurs collections Directus en une seule exécution.
    Gestion des Images : Télécharge automatiquement les fichiers médias depuis Directus et les upload sur Zenodo.
    Rétro-écriture Intelligente (Write-Back) :
        Détecte automatiquement les champs zenodo_doi et zenodo_record_url dans vos tables Directus.
        Met à jour vos fiches Directus avec le DOI et l'URL du dépôt Zenodo dès la création.
        Sécurité : Bloque la synchronisation si les champs de retour sont manquants, évitant ainsi les erreurs silencieuses.
    Interface Moderne : Dashboard interactif en temps réel avec logs détaillés.
    Respect de la Vie Privée : 100% auto-hébergeable, aucun tiers n'accède à vos données.

📋 Prérequis

    Python 3.9 ou supérieur
    Directus (v9.0+) avec un token d'administration
    Zenodo (Compte Sandbox ou Production) avec un token API
    Accès SSH (pour le déploiement sur serveur)

🚀 Installation Locale (Développement)

    Cloner le dépôt

    bash
    git clone https://github.com/cypac05/sanctuaire-sync.git
    cd sanctuaire-sync

    Créer un environnement virtuel

    bash
    python3 -m venv venv
    source venv/bin/activate  # Sur Mac/Linux
    # ou
    venv\Scripts\activate     # Sur Windows

    Installer les dépendances

    bash
    pip install -r requirements.txt

    Lancer le serveur

    bash
    python main.py

    L'interface est maintenant accessible sur http://127.0.0.1:8000.

🛠️ Utilitaires de Maintenance

Le dépôt inclut un script de nettoyage pour gérer les tests sur Zenodo Sandbox.
Nettoyer Zenodo Sandbox (clean_sandbox.py)

Ce script supprime tous les dépôts associés à votre token API sur l'environnement de test (Sandbox). Utile pour repartir à zéro après des sessions de tests intensifs.

Attention : Cette action est irréversible.

    Éditez le fichier clean_sandbox.py et remplacez VOTRE_TOKEN_SANDBOX_ICI par votre token Zenodo Sandbox.
    Lancez le script :

    bash
    python clean_sandbox.py

    Confirmez en tapant oui.

Le script gère la pagination de l'API et tente de supprimer même les dépôts corrompus ou "metadata only".
🐳 Déploiement sur Serveur (VPS Infomaniak)

Pour une utilisation en production, il est recommandé d'utiliser Docker sur un VPS Cloud ou VPS Lite Infomaniak.
1. Préparer le serveur

Connectez-vous en SSH à votre VPS et installez Docker :

bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

2. Construire et lancer le conteneur

À la racine du projet (où se trouve le Dockerfile) :

bash
# Construire l'image
docker build -t sanctuaire-sync .

# Lancer le conteneur
docker run -d -p 8000:8000 --name sync-app sanctuaire-sync

3. Configurer le Reverse Proxy (Optionnel mais recommandé)

Pour exposer le service en HTTPS (via Nginx et Let's Encrypt), configurez votre VPS pour rediriger le domaine vers le port 8000.
⚙️ Configuration dans Directus

Pour que la rétro-écriture (DOI/URL) fonctionne, vous devez ajouter deux champs Texte dans chacune de vos collections à synchroniser :

    zenodo_doi : Pour stocker l'identifiant DOI (ex: 10.5072/zenodo.12345).
    zenodo_record_url : Pour stocker l'URL publique du dépôt (ex: https://sandbox.zenodo.org/records/12345).

    Note : Si ces champs sont absents, l'application affichera une erreur critique dans les logs et refusera de synchroniser la table concernée pour éviter la perte de données.

📄 Structure du Projet

plain text
sanctuaire-sync/
├── main.py              # Backend FastAPI (Logique de sync & API)
├── index.html           # Frontend Vue.js (Interface utilisateur)
├── clean_sandbox.py     # Script utilitaire de nettoyage Zenodo
├── requirements.txt     # Dépendances Python
├── Dockerfile           # Configuration pour conteneurisation
└── README.md            # Ce fichier

📜 Licence

Projet open-source développé pour le Sanctuaire Non-OGM. Hébergé sur infrastructure éthique et respectueuse de la vie privée.
