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

class TableConfig(BaseModel):
    """Configuration spécifique pour une seule table"""
    name: str
    title_field: str
    selected_fields: List[str]

class SyncConfig(BaseModel):
    """Configuration globale de synchronisation"""
    directus_url: str
    directus_token: str
    zenodo_url: str
    zenodo_token: str
    collections: List[TableConfig]

# --- Gestion du Cycle de Vie ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    log_message("Démarrage du serveur Sanctuaire Sync (Mode Proxy Multi-Tables)...")
    yield
    log_message("Arrêt du serveur.")

app = FastAPI(lifespan=lifespan, title="Sanctuaire Sync API")

# --- Middleware CORS ---
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
        file_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=500, detail="Fichier index.html introuvable.")
    return FileResponse(file_path)

@app.get("/api/logs")
async def get_logs():
    return {"logs": log_buffer, "running": is_running}

# --- Route Proxy Universel ---
@app.api_route("/api/proxy/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_directus(path: str, request: Request):
    headers = dict(request.headers)
    exclude_headers = ["host", "content-length", "connection", "transfer-encoding", "accept-encoding"]
    clean_headers = {k: v for k, v in headers.items() if k.lower() not in exclude_headers}
    
    body = await request.body()
    target_base_url = headers.get("x-target-url")
    
    if not target_base_url:
        raise HTTPException(status_code=400, detail="Header X-Target-Url manquant.")
    
    target_base_url = target_base_url.rstrip("/")
    target_url = f"{target_base_url}/{path}"
    
    log_message(f"🔄 Proxy : {request.method} {target_url}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=clean_headers,
                content=body,
                params=request.query_params
            )
            
            return JSONResponse(
                status_code=resp.status_code,
                content=resp.json() if resp.content else {},
                headers=dict(resp.headers)
            )
        except httpx.ConnectError:
            log_message(f"❌ Impossible de se connecter à {target_base_url}", "ERROR")
            raise HTTPException(status_code=503, detail=f"Impossible de joindre Directus à {target_base_url}")
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
    log_message(f"Tables à traiter : {[c.name for c in config.collections]}")
    
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

            for table_config in config.collections:
                collection_name = table_config.name
                title_field = table_config.title_field
                selected_fields = table_config.selected_fields
                
                log_message(f"📂 Traitement de la table : {collection_name}")
                log_message(f"   -> Champ titre : {title_field}")
                log_message(f"   -> Champs inclus : {len(selected_fields)}")
                
                try:
                    url = f"{config.directus_url}/items/{collection_name}?limit=100"
                    resp = await client.get(url, headers=headers)
                    resp.raise_for_status()
                    items = resp.json().get('data', [])
                    
                    log_message(f"   ✅ {len(items)} éléments trouvés.")
                    
                    if not items:
                        log_message(f"   ⚠️ Rien à synchroniser dans '{collection_name}'.")
                        continue

                    for i, item in enumerate(items):
                        mapping = {
                            "title_field": title_field,
                            "selected_fields": selected_fields
                        }
                        metadata = prepare_zenodo_metadata(item, mapping, collection_name)
                        
                        if metadata:
                            log_message(f"   📤 Envoi vers Zenodo : {metadata.get('title', 'Sans titre')}")
    
                        try:
                            # 1. Préparer la requête
                            headers_zenodo = {"Authorization": f"Bearer {config.zenodo_token}"}
                            data = {'metadata': metadata}
        
                                # 2. Envoyer à l'API Zenodo pour créer un brouillon (Deposition)
                                async with httpx.AsyncClient(timeout=30.0) as zenodo_client:
                                res = await zenodo_client.post(
                                f"{config.zenodo_url}/api/deposit/depositions", 
                                json=data, 
                                headers=headers_zenodo
                             )
            
                            # 3. Vérifier la réponse
                            res.raise_for_status()
                            result = res.json()
            
                            deposition_id = result.get('id')
                            html_link = result.get('links', {}).get('html', 'Inconnu')
            
                            log_message(f"   ✅ Dépôt créé ! ID: {deposition_id}")
                            log_message(f"   🔗 Lien : {html_link}")
                            total_success += 1
            
                    except Exception as zenodo_err:
                        log_message(f"   ❌ Erreur Zenodo : {str(zenodo_err)}")
                        total_errors += 1
                        else:
                            log_message(f"   ⚠️ Élément ignoré (champ titre manquant).")
                            total_errors += 1
                            
                except Exception as e:
                    log_message(f"   ❌ Erreur critique sur '{collection_name}': {str(e)}")
                    total_errors += 1

            log_message(f"🎉 TERMINÉ ! Résumé : {total_success} succès, {total_errors} échecs/ignorés.")

    except Exception as e:
        log_message(f"❌ Erreur globale : {str(e)}")
    finally:
        is_running = False

def prepare_zenodo_metadata(item: Dict, mapping: Dict, collection_name: str) -> Dict:
    """Transforme un item Directus en métadonnées Zenodo selon la config de la table"""
    title_field = mapping.get('title_field')
    
    if not title_field or title_field not in item:
        return None
    
    title = item[title_field]
    desc_parts = []
    
    for field in mapping.get('selected_fields', []):
        if field in item and item[field] is not None:
            desc_parts.append(f"**{field}**: {item[field]}")
    
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
