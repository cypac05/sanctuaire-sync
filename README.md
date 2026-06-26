🌱 Sanctuaire Sync

Sanctuaire Sync est un outil de synchronisation automatique conçu pour exporter des données depuis une instance Directus vers Zenodo (ou Zenodo Sandbox). Il permet de créer des dépôts scientifiques (datasets) complets, incluant les métadonnées structurées et les fichiers images associés, le tout en respectant les principes de science ouverte.
✨ Fonctionnalités

    Sélection Multi-Tables : Synchronisez plusieurs collections Directus en une seule fois.
    Configuration Granulaire : Pour chaque table, définissez indépendamment :
        Le champ utilisé comme Titre du dépôt Zenodo.
        Les champs à inclure dans la Description.
        Jusqu'à deux champs Images à joindre automatiquement au dépôt.
    Proxy CORS Intégré : Contourne les restrictions de sécurité des navigateurs pour se connecter à n'importe quelle instance Directus (locale ou distante) sans configuration serveur complexe.
    Gestion Intelligente des Images : Détection automatique des types de champs, téléchargement sécurisé depuis Directus et upload vers Zenodo.
    Sauvegarde Locale : Votre configuration (URL, tokens, sélections) est sauvegardée dans votre navigateur pour une utilisation ultérieure rapide.

📋 Prérequis
1. Côté Directus

Vous devez avoir une instance Directus fonctionnelle avec :

    Un Token Admin (ou un token utilisateur avec accès en lecture aux collections et aux fichiers).
    Les collections contenant vos données.
    (Optionnel mais recommandé) Des champs de type "Fichier" ou "Image" pour les illustrations.

⚙️ Configuration dans Directus

Pour que la synchronisation fonctionne et que les références soient sauvegardées en retour, vous devez ajouter deux champs spécifiques dans chaque collection à synchroniser.
A. Champs de Contenu (Source)

Ces champs contiennent les données à envoyer :

    Champ Titre : Un champ texte (ex: nom_variete, titre_projet).
    Champs Descriptifs : Tous les champs texte que vous souhaitez voir apparaître dans la notice Zenodo.
    Champs Images : Un ou deux champs de type Fichier ou Image (Interface: file-input ou image).

B. Champs de Retour (Destination) - OBLIGATOIRES

Ces champs sont nécessaires pour que Sanctuaire Sync puisse enregistrer le résultat de l'export dans Directus après la création du dépôt Zenodo. Créez-les dans chaque collection concernée :
Nom du Champ (Slug)	Type	Interface	Rôle
zenodo_doi	String	Input	Reçoit le DOI unique (ex: 10.5072/zenodo.12345) après publication.
zenodo_record_url	String	Input	Reçoit l'URL directe vers le dépôt (ex: https://sandbox.zenodo.org/record/12345).

    Note importante : Actuellement, l'outil crée les dépôts en mode "Brouillon" sur Zenodo. Le DOI final n'est attribué qu'au moment de la publication (bouton "Submit" sur le site Zenodo).

        Option 1 (Manuelle) : Vous publiez sur Zenodo, copiez le DOI et l'URL, et les collez dans Directus.
        Option 2 (Automatique - À venir) : Une future mise à jour pourra écrire automatiquement ces champs via l'API Directus après la publication.


2. Côté Zenodo

    Un compte sur Zenodo ou Zenodo Sandbox (pour les tests).
    Un Token API personnel :
        Allez dans Settings > Applications > Create new token.
        Donnez-lui un nom (ex: Sanctuaire Sync).
        Cochez les permissions : deposit:actions et deposit:write.
        Copiez le token généré.

3. Côté Système

    Python 3.8 ou supérieur.
    Git (pour cloner le dépôt).

🚀 Installation et Démarrage
1. Cloner le projet

bash
git clone https://github.com/cypac05/sanctuaire-sync.git
cd sanctuaire-sync

2. Créer un environnement virtuel

bash
# Sur Mac/Linux
python3 -m venv venv
source venv/bin/activate

# Sur Windows
python -m venv venv
venv\Scripts\activate

3. Installer les dépendances

bash
pip install -r requirements.txt

Note : Si vous rencontrez une erreur httpx, installez-le manuellement : pip install httpx.
4. Lancer le serveur

bash
python main.py

Le serveur démarre sur http://localhost:8000.
5. Ouvrir l'interface

Ouvrez votre navigateur et allez sur : http://localhost:8000
⚙️ Configuration dans Directus

Pour que la synchronisation fonctionne optimalement, assurez-vous que vos collections Directus sont structurées comme suit. Aucune modification technique n'est requise dans le schéma, mais la présence de certains champs est nécessaire pour l'export.
Champs Recommandés (Métadonnées)

Bien que l'outil puisse utiliser n'importe quel champ texte, il est recommandé d'avoir :

    Un champ Titre (Type: String ou Input) : Pour identifier clairement l'élément.
    Un champ Description (Type: Text ou Textarea) : Pour le résumé scientifique.
    Des champs spécifiques à votre domaine (ex: Nom_Latin, Lieu_Origine, Date_Recolte).

Champs Requis pour les Images

Pour utiliser la fonctionnalité d'upload d'images, vous devez avoir dans votre collection au moins un champ de type Fichier ou Image.

    Type de champ : Dans Directus, le type doit être UUID (pour la relation) et l'interface doit être File Input ou Image.
    Configuration : L'outil détecte automatiquement ces champs dans la liste déroulante de configuration (filtrée par l'icône 📷).

    Note : Si vos champs images n'apparaissent pas dans la liste déroulante de l'interface Sanctuaire Sync, vérifiez dans Directus que leur interface est bien définie sur file-input, file-image ou image.

📖 Utilisation

    Connexion :
        Entrez l'URL de votre Directus (ex: https://directus.monsite.com) et le Token.
        Entrez l'URL de Zenodo (https://sandbox.zenodo.org pour tester) et le Token API.
        Cliquez sur Tester la connexion.

    Sélection des Tables :
        Cliquez sur Charger la liste des tables.
        Cochez les collections que vous souhaitez exporter.

    Configuration par Table :
        Cliquez sur l'onglet d'une table sélectionnée.
        Champs de données : Cochez les champs à inclure dans la description du dépôt.
        Champ Titre : Sélectionnez le champ qui servira de titre principal.
        Champ Image 1 / Image 2 : Sélectionnez les champs contenant les images à joindre (la liste ne montre que les champs compatibles).
        Répétez pour chaque table.

    Lancement :
        Cliquez sur 🚀 Lancer la Sync.
        Suivez la progression dans le terminal intégré.
        Une fois terminé, connectez-vous à Zenodo pour vérifier vos brouillons ("Drafts").

🛠️ Dépannage

    Erreur 404 sur Directus : Vérifiez que l'URL ne se termine pas par un slash / (ex: utilisez https://.../api et non https://.../api/). L'outil tente de corriger cela automatiquement, mais une URL propre est préférable.
    Erreur "Illegal header value" : Cela vient souvent d'espaces invisibles dans le Token Zenodo. Régénérez un token et copiez-le soigneusement. L'outil applique maintenant un nettoyage automatique (.strip()).
    Les images ne s'uploadent pas : Vérifiez que le token Directus a bien les droits de lecture sur la table directus_files (ou que les images sont publiques). Les logs indiqueront "Échec upload image" avec la raison précise.
    Rien n'apparaît dans Zenodo : Assurez-vous d'utiliser le bon environnement (Sandbox vs Production). Un dépôt créé sur Sandbox n'apparaîtra pas sur le site principal de Zenodo.

📄 Licence

Ce projet est distribué sous licence MIT.
🤝 Contributeurs

Développé pour le projet Sanctuaire Non-OGM. Basé sur les technologies FastAPI, Vue.js 3, TailwindCSS et les API Directus & Zenodo.
Prochaine étape suggérée :

