import os
import asyncio
import logging
from typing import List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx

# --- Configuration des Logs ---
# On utilise une liste en mémoire pour stocker les logs accessibles par l'API
log_buffer: List[str] = []
is_running = False

def log_message(message: str, level: str = "INFO"):
    """Ajoute un message au buffer de logs et l'affiche dans la console serveur."""
    formatted_msg = f"[{level}] {message}"
    log_buffer.append(formatted_msg)
    # Garde seulement les 200 derniers logs pour ne pas saturer la mémoire
    if len(log_buffer) > 200:
        log_buffer.pop(0)
    print(formatted_msg)

# --- Modèles de Données ---
class SyncConfig(BaseModel):
    directus_url: str
    directus_token: str
    zenodo_url: str
    zenodo_token: str
    collection: str
    fields_mapping: Dict[str, Any]

# --- Gestion du Cycle de Vie (Startup/Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log_message("Démarrage du serveur Sanctuaire Sync...")
    yield
    # Shutdown
    log_message("Arrêt du serveur.")

app = FastAPI(lifespan=lifespan, title="Sanctuaire Sync API")

# --- Middleware CORS (Pour permettre à l'interface de communiquer) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En prod, restreindre aux domaines autorisés
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routes API ---

@app.get("/")
async def read_root():
    """Sert le fichier index.html"""
    return FileResponse('index.html')

@app.get("/api/logs")
async def get_logs():
    """Renvoie les logs actuels et l'état d'exécution"""
    return {"logs": log_buffer, "running": is_running}

@app.post("/api/start-sync")
async def start_sync(config: SyncConfig, background_tasks: BackgroundTasks):
    """Lance la synchronisation en tâche de fond"""
    global is_running
    
    if is_running:
        raise HTTPException(status_code=400, detail="Une synchronisation est déjà en cours")
    
    # Vider les anciens logs pour une nouvelle session propre
    log_buffer.clear()
    log_message("Nouvelle session de synchronisation démarrée")
    log_message(f"Collection cible: {config.collection}")
    
    is_running = True
    background_tasks.add_task(run_sync_process, config)
    
    return {"status": "started", "message": "Synchronisation lancée en arrière-plan"}

# --- Logique de Synchronisation (Cœur du système) ---

async def run_sync_process(config: SyncConfig):
    global is_running
    try:
        log_message("🔍 Connexion à Directus pour récupérer les données...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers_directus = {
                "Authorization": f"Bearer {config.directus_token}",
                "Content-Type": "application/json"
            }
            
            # 1. Récupérer les items de la collection
            # Note: On limite à 100 pour l'exemple, à adapter avec pagination si besoin
            url_items = f"{config.directus_url}/items/{config.collection}"
            params = {"limit": 100} 
            
            response = await client.get(url_items, headers=headers_directus, params=params)
            response.raise_for_status()
            
            items = response.json().get('data', [])
            log_message(f"✅ {len(items)} éléments récupérés de Directus.")
            
            if not items:
                log_message("⚠️ Aucun élément à synchroniser.")
                is_running = False
                return

            # 2. Boucle de synchronisation vers Zenodo
            success_count = 0
            error_count = 0
            
            for i, item in enumerate(items):
                log_message(f"Traitement de l'élément {i+1}/{len(items)}...")
                
                # Préparer les métadonnées pour Zenodo selon le mapping
                metadata = prepare_zenodo_metadata(item, config.fields_mapping)
                
                if not metadata:
                    log_message(f"⚠️ Élément {i+1} ignoré (données insuffisantes).")
                    continue

                try:
                    # Simulation d'envoi à Zenodo (À remplacer par le vrai appel API Zenodo)
                    # Pour l'instant, on logue juste ce qui serait envoyé
                    log_message(f"📤 Envoi vers Zenodo: {metadata.get('title', 'Sans titre')}")
                    
                    # --- ICI : Vrai appel API Zenodo ---
                    # headers_zenodo = {"Authorization": f"Bearer {config.zenodo_token}"}
                    # data = {'metadata': metadata}
                    # res = await client.post(f"{config.zenodo_url}/api/deposit/depositions", json=data, headers=headers_zenodo)
                    # res.raise_for_status()
                    
                    await asyncio.sleep(1) # Simulation de délai réseau
                    log_message(f"✅ Élément {i+1} synchronisé avec succès.")
                    success_count += 1
                    
                except Exception as e:
                    log_message(f"❌ Erreur pour l'élément {i+1}: {str(e)}")
                    error_count += 1

            log_message("🎉 Synchronisation terminée !")
            log_message(f"Résumé : {success_count} succès, {error_count} échecs.")

    except Exception as e:
        log_message(f"❌ Erreur critique du processus : {str(e)}")
    finally:
        is_running = False

def prepare_zenodo_metadata(item: Dict, mapping: Dict) -> Dict:
    """Transforme un item Directus en métadonnées Zenodo"""
    title_field = mapping.get('title_field')
    selected_fields = mapping.get('selected_fields', [])
    
    if not title_field or title_field not in item:
        return None
        
    title = item[title_field]
    
    # Construction de la description basée sur les champs sélectionnés
    description_parts = []
    for field in selected_fields:
        if field in item and item[field] is not None:
            description_parts.append(f"**{field}**: {item[field]}")
    
    description = "\n".join(description_parts) if description_parts else "Aucune description détaillée."
    
    return {
        "title": title,
        "description": description,
        "upload_type": "dataset",
        "access_right": "open",
        "license": "cc-by-4.0",
        # Ajoutez ici les créateurs, keywords, etc. si disponibles dans l'item
        "creators": [{"name": "Sanctuaire Non-OGM Sync"}]
    }

if __name__ == "__main__":
    import uvicorn
    # Lance le serveur sur le port 8000 par défaut
    uvicorn.run(app, host="0.0.0.0", port=8000)
