# 🌱 Sanctuaire Non-OGM – Outil de Synchronisation Zenodo

Outil autonome et sécurisé pour sanctuariser vos collections de semences (Directus) sur la plateforme **Zenodo** (CERN). Il génère automatiquement des **DOI** (Digital Object Identifiers) et des fichiers de preuve horodatés pour établir une **antériorité incontestable** face aux brevets sur le vivant.

## ✨ Fonctionnalités

*   **Profils Nommés** : Sauvegardez plusieurs configurations (une par instance Directus) et passez de l'une à l'autre en un clic.
*   **Preuve d'Antériorité Juridique** : Chaque accession reçoit un DOI unique et inaltérable hébergé par le CERN.
*   **Fichier de Preuve Automatique** : Génération et upload d'un fichier texte contenant l'empreinte exacte des données à l'instant T.
*   **Synchronisation Bidirectionnelle** : Mise à jour automatique de votre base Directus avec les DOI et liens Zenodo.
*   **100% Local & Sécurisé** : L'outil s'exécute sur votre machine. Vos tokens et données sensibles ne transitent que vers Zenodo/Directus.
*   **Multi-Plateforme** : Compatible Windows, macOS et Linux.
*   **Zéro Configuration Complexe** : Installation automatique des dépendances au premier lancement.

---

## 🚀 Installation & Lancement (3 étapes)

### 1. Prérequis : Python
Vous devez avoir **Python** installé sur votre ordinateur.
*   📥 [Télécharger Python ici](https://www.python.org/downloads/)
*   ⚠️ **IMPORTANT (Windows)** : Lors de l'installation, cochez impérativement la case **"Add Python to PATH"** en bas de la fenêtre.

### 2. Téléchargement de l'outil
1.  Cliquez sur le bouton vert **`<> Code`** en haut de cette page.
2.  Cliquez sur **`Download ZIP`**.
3.  **Extrayez** (dézippez) le dossier téléchargé sur votre **Bureau**.
    *   *Le dossier doit s'appeler `sanctuaire-sync-main` (ou similaire).*

### 3. Lancement
Ouvrez le dossier extrait et double-cliquez sur le fichier correspondant à votre système :

*   🪟 **Windows** : Double-cliquez sur **`Lancer.bat`**.
*   🍎 **macOS** / 🐧 **Linux** : Ouvrez un terminal dans le dossier et tapez :
    ```bash
    chmod +x Lancer.sh
    ./Lancer.sh
    ```

🌐 L'application s'ouvrira automatiquement dans votre navigateur à l'adresse `http://localhost:8765`.

---

## 📖 Comment l'utiliser ?

Une fois l'interface ouverte dans votre navigateur :

1.  **Profils de configuration** :
    *   Créez un profil par instance Directus avec le bouton **`+ Nouveau`**.
    *   Sauvegardez votre configuration avec **`💾 Sauvegarder`** (les profils sont stockés localement dans le dossier `configs/`).
    *   Passez d'un profil à l'autre via le menu déroulant en haut de page.
2.  **Configuration Directus** :
    *   **URL** : L'adresse de votre instance (ex: `http://localhost:8058` ou `https://db.monsite.com`).
    *   **Token** : Votre token d'administration Directus (créé dans votre profil utilisateur).
2.  **Configuration Zenodo** :
    *   **URL** : `https://sandbox.zenodo.org` (pour tester) ou `https://zenodo.org` (pour la production).
    *   **Token** : Votre token d'application Zenodo (créé dans *Settings > Applications*).
3.  **Sélection des Données** :
    *   **Collection** : Le nom de la table dans Directus (ex: `Variete`, `Accessions`).
    *   **Champ Titre** : Le champ à utiliser comme nom principal (ex: `Nom`).
4.  **Lancement** :
    *   Cliquez sur **🚀 Lancer la Synchronisation**.
    *   Suivez la progression en temps réel dans la console.
    *   À la fin, vos items dans Directus auront un nouveau DOI et un lien vers la preuve publique.

> **Note** : L'outil ignore automatiquement les items qui possèdent déjà un DOI (champ `zenodo_doi` rempli).

---

## 🛑 Comment arrêter l'application ?

*   Fermez simplement la **fenêtre noire (terminal)** qui s'est ouverte lors du lancement.
*   Le serveur s'arrêtera immédiatement.

---

## 🔒 Sécurité & Confidentialité

*   **Tokens & Profils** : Vos tokens API et configurations sont sauvegardés dans le dossier `configs/` sur votre machine. Ce dossier est exclu du dépôt Git (`.gitignore`) — vos informations sensibles ne sont jamais publiées.
*   **Données** : Aucune donnée n'est collectée par les développeurs de cet outil. Tout reste entre votre machine, votre instance Directus et Zenodo.
*   **Code Open Source** : Le code est auditable publiquement sur ce dépôt GitHub.

---

## 🛠️ Dépannage (FAQ)

**❌ Erreur : "Python n'est pas reconnu"**
*   Vous n'avez pas coché "Add Python to PATH" lors de l'installation. Désinstallez Python, réinstallez-le en cochant la case, et réessayez.

**❌ Erreur : "Port déjà utilisé"**
*   Une autre instance de l'application est déjà ouverte. Fermez la fenêtre terminal correspondante ou changez de port dans le code `main.py`.

**❌ Erreur : "Permission denied" (Zenodo)**
*   Votre token Zenodo n'a pas les droits suffisants. Vérifiez qu'il a bien les scopes `deposit:actions` et `deposit:write`.

**❌ Erreur : "CORS" ou connexion refusée**
*   Vérifiez que l'URL de votre Directus est correcte et accessible depuis votre navigateur.

---

## 📄 Licence

Ce projet est distribué sous licence **MIT**. Vous êtes libre de l'utiliser, le modifier et le distribuer pour vos propres projets de souveraineté semencière.

*Développé pour le projet Sanctuaire Non-OGM.*
