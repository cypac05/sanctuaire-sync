import os
import asyncio
import logging
from typing import List, Dict, Any
from contextlib import asynccontextmanager
from urllib.parse import urljoin

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel
import httpx

# --- Configuration des Logs ---
log_buffer: List[str] = []
is_running = False

def log_message(message: str, level: str = "INFO"):
    formatted_msg = f"[{level}] {message}"
    log_buffer.append(formatted_msg)
    if len(log_buffer) > 200:
        log_buffer.pop(0)
    print(formatted_msg)

# --- Modèles de Données ---
class SyncConfig(BaseModel):
    directus_url: str
    directus_token: str
    zenodo_url: str
    zenodo_token: str
    collections: List[str]  # DEVIENT UNE LISTE
    fields_mapping: Dict[str, Any]

# --- Gestion du Cycle de Vie ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    log_message("Démarrage du serveur Sanctuaire Sync (Mode Proxy)...")
    yield
    log_message("Arrêt du serveur.")

app = FastAPI(lifespan=lifespan, title="Sanctuaire Sync API")

# --- Middleware CORS (Pour que le navigateur accepte de parler à Python) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routes Principales ---

@app.get("/")
async def read_root():
    file_path = os.path.join(os.path.dirname(__file__), "index.html")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=500, detail="Fichier index.html introuvable.")
    return FileResponse(file_path)

@app.get("/api/logs")
async def get_logs():
    return {"logs": log_buffer, "running": is_running}

# --- NOUVEAU : Le Proxy Universel ---
# Cette route attrape toutes les demandes vers Directus et les transmet
@app.api_route("/api/proxy/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_directus(path: str, request: Request):
    # 1. Récupérer les headers de la demande originale (surtout l'Authorization)
    headers = dict(request.headers)
    
    # On retire certains headers qui posent problème en transfert (host, content-length, etc.)
    exclude_headers = ["host", "content-length", "connection", "transfer-encoding", "accept-encoding"]
    clean_headers = {k: v for k, v in headers.items() if k.lower() not in exclude_headers}
    
    # 2. Récupérer le corps de la demande si présent (pour les POST/PUT)
    body = await request.body()
    
    # 3. Reconstruire l'URL cible (Directus)
    # L'URL de Directus est passée dans un header personnalisé 'X-Target-Url' envoyé par le frontend
    target_base_url = headers.get("x-target-url")
    
    if not target_base_url:
        raise HTTPException(status_code=400, detail="Header X-Target-Url manquant. Configuration incorrecte.")
    
    # Nettoyer l'URL de base (enlever le slash final s'il y en a un)
    target_base_url = target_base_url.rstrip("/")
    target_url = f"{target_base_url}/{path}"
    
    log_message(f"🔄 Proxy : {request.method} {target_url}")

    # 4. Transmettre la demande à Directus
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=clean_headers,
                content=body,
                params=request.query_params
            )
            
            # 5. Renvoyer la réponse de Directus au navigateur
            return JSONResponse(
                status_code=resp.status_code,
                content=resp.json() if resp.content else {},
                headers=dict(resp.headers)
            )
        except httpx.ConnectError:
            log_message(f"❌ Impossible de se connecter à {target_base_url}", "ERROR")
            raise HTTPException(status_code=503, detail=f"Impossible de joindre Directus à l'adresse {target_base_url}")
        except Exception as e:
            log_message(f"❌ Erreur Proxy: {str(e)}", "ERROR")
            raise HTTPException(status_code=500, detail=str(e))

# --- Logique de Synchronisation ---

@app.post("/api/start-sync")
async def start_sync(config: SyncConfig, background_tasks: BackgroundTasks):
    global is_running
    if is_running:
        raise HTTPException(status_code=400, detail="Synchro en cours")
    
    log_buffer.clear()
    log_message("Nouvelle session démarrée")
    log_message(f"Collection: {config.collection}")
    
    is_running = True
    background_tasks.add_task(run_sync_process, config)
    return {"status": "started"}

async def run_sync_process(config: SyncConfig):
    global is_running
    try:
        log_message("🔍 Connexion à Directus...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {config.directus_token}"}
            
            total_success = 0
            total_errors = 0

            # BOUCLE SUR TOUTES LES TABLES SÉLECTIONNÉES
            for collection_name in config.collections:
                log_message(f"📂 Traitement de la table : {collection_name}")
                
                try:
                    url = f"{config.directus_url}/items/{collection_name}?limit=100"
                    resp = await client.get(url, headers=headers)
                    resp.raise_for_status()
                    items = resp.json().get('data', [])
                    
                    log_message(f"   ✅ {len(items)} éléments trouvés dans '{collection_name}'.")
                    
                    if not items:
                        log_message(f"   ⚠️ Rien à synchroniser dans '{collection_name}'.")
                        continue

                    # Boucle sur les items de CETTE table
                    for i, item in enumerate(items):
                        # log_message(f"   Traitement {i+1}/{len(items)}...") # Trop verbeux, on garde pour la fin
                        metadata = prepare_zenodo_metadata(item, config.fields_mapping, collection_name)
                        
                        if metadata:
                            log_message(f"   📤 Envoi : {metadata.get('title', 'Sans titre')} ({collection_name})")
                            # Simulation Zenodo
                            await asyncio.sleep(0.2) 
                            log_message(f"   ✅ Succès.")
                            total_success += 1
                        else:
                            total_errors += 1
                            
                except Exception as e:
                    log_message(f"   ❌ Erreur critique sur la table '{collection_name}': {str(e)}")
                    total_errors += 1

            log_message(f"🎉 TERMINÉ ! Résumé : {total_success} succès, {total_errors} échecs/ignorés.")

    except Exception as e:
        log_message(f"❌ Erreur globale : {str(e)}")
    finally:
        is_running = False

def prepare_zenodo_metadata(item: Dict, mapping: Dict, collection_name: str) -> Dict:
    title_field = mapping.get('title_field')
    # Sécurité : si le champ titre n'existe pas dans cet item (car champs différents selon tables)
    if not title_field or title_field not in item:
        return None
    
    title = item[title_field]
    desc_parts = []
    
    for field in mapping.get('selected_fields', []):
        # On ajoute le champ seulement s'il existe dans CET item
        if field in item and item[field] is not None:
            desc_parts.append(f"**{field}**: {item[field]}")
    
    # Ajout de la collection source dans la description pour traçabilité
    desc_parts.append(f"**Source**: Table '{collection_name}'")
    
    return {
        "title": f"[{collection_name}] {title}",
        "description": "\n".join(desc_parts) if desc_parts else "Données synchronisées via Sanctuaire Sync",
        "upload_type": "dataset",
        "access_right": "open",
        "license": "cc-by-4.0",
        "creators": [{"name": "Sanctuaire Non-OGM"}]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
