@echo off
chcp 65001 >nul
:: Sanctuaire Non-OGM – Outil de Synchronisation Zenodo
:: Script de lancement pour Windows

:: Se placer dans le dossier du script
cd /d "%~dp0"

:: Vérifier que Python est disponible
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Python n'est pas installe.
    echo Veuillez l'installer depuis https://www.python.org/downloads/
    echo N'oubliez pas de cocher "Add Python to PATH" lors de l'installation !
    pause
    exit /b 1
)

:: Créer l'environnement virtuel si nécessaire
if not exist "venv" (
    echo Premiere utilisation : creation de l'environnement Python...
    python -m venv venv
)

:: Activer l'environnement virtuel
call venv\Scripts\activate.bat

:: Installer / mettre à jour les dépendances
echo Verification des dependances...
pip install -q -r requirements.txt

:: Créer le dossier configs si absent
if not exist "configs" mkdir configs

:: Ouvrir le navigateur
start "" http://localhost:8765

echo.
echo  Sanctuaire Non-OGM - Synchronisation Zenodo
echo  =============================================
echo  Interface disponible sur : http://localhost:8765
echo  (Fermez cette fenetre pour arreter le serveur)
echo.

python main.py

pause
