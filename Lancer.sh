#!/bin/bash
# Sanctuaire Non-OGM – Outil de Synchronisation Zenodo
# Script de lancement pour macOS et Linux

# Se placer dans le dossier du script
cd "$(dirname "$0")"

# Vérifier que Python 3 est disponible
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé."
    echo "   Veuillez l'installer depuis https://www.python.org/downloads/"
    read -p "Appuyez sur Entrée pour quitter..."
    exit 1
fi

# Créer l'environnement virtuel si nécessaire
if [ ! -d "venv" ]; then
    echo "⚙️  Première utilisation : création de l'environnement Python..."
    python3 -m venv venv
fi

# Activer l'environnement virtuel
source venv/bin/activate

# Installer / mettre à jour les dépendances
echo "📦 Vérification des dépendances..."
pip install -q -r requirements.txt

# Créer le dossier configs si absent (pour les profils)
mkdir -p configs

# Ouvrir le navigateur après un court délai
(
    sleep 2
    if command -v open &> /dev/null; then
        open http://localhost:8765       # macOS
    elif command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:8765   # Linux
    fi
) &

echo ""
echo "🌱 Sanctuaire Non-OGM – Synchronisation Zenodo"
echo "================================================"
echo "🌐 Interface disponible sur : http://localhost:8765"
echo "   (Ctrl+C pour arrêter)"
echo ""

python3 main.py
