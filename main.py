import os
import asyncio
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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
    image1_field: Optional[str] = None
    image2_field: Optional[str] = None
    doi_field: Optional[str] = None
    url_field: Optional[str] = None

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
    log_message("Démarrage du serveur Sanctuaire Sync (Auto-DOI + Filtre Images)...")
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

async def update_directus_record(directus_url: str, token: str, collection: str, item_id: str, doi: str, url: str, doi_field: str, url_field: str):
    """Met à jour l'élément Directus avec le DOI et l'URL reçus de Zenodo"""
    try:
        payload = {}
        if doi_field and doi:
            payload[doi_field] = doi
        if url_field and url:
            payload[url_field] = url
            
        if not payload:
            return

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            resp = await client.patch(
                f"{directus_url}/items/{collection}/{item_id}",
                json=payload,
                headers=headers
            )
            resp.raise_for_status()
            log_message(f"   ✅ Directus mis à jour (DOI: {doi if doi else 'N/A'}, URL: {url if url else 'N/A'})")
    except Exception as e:
        log_message(f"   ⚠️ Échec mise à jour Directus : {str(e)}")

async def run_sync_process(config: SyncConfig):
    global is_running
    try:
        log_message("🔍 Connexion à Directus...")
        directus_url = config.directus_url.rstrip("/")
        zenodo_url = config.zenodo_url.rstrip("/")
        clean_token = config.zenodo_token.strip()

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {config.directus_token}"}
            
            total_success = 0
            total_errors = 0
            total_skipped = 0

            for table_config in config.collections:
                collection_name = table_config.name
                
                # --- ÉTAPE 1 : VÉRIFICATION AUTOMATIQUE DES CHAMPS DE RETOUR ---
                log_message(f"📂 Vérification de la table : {collection_name}")
                
                url_fields_check = f"{directus_url}/fields/{collection_name}"
                resp_fields = await client.get(url_fields_check, headers=headers)
                
                existing_fields = []
                if resp_fields.status_code == 200:
                    fields_data = resp_fields.json().get('data', [])
                    existing_fields = [f['field'] for f in fields_data]
                
                expected_doi_field = "zenodo_doi"
                expected_url_field = "zenodo_record_url"
                
                missing_fields = []
                
                if expected_doi_field not in existing_fields:
                    missing_fields.append(expected_doi_field)
                else:
                    table_config.doi_field = expected_doi_field
                    
                if expected_url_field not in existing_fields:
                    missing_fields.append(expected_url_field)
                else:
                    table_config.url_field = expected_url_field

                if missing_fields:
                    log_message(f"   ❌ ERREUR CRITIQUE pour '{collection_name}' : Champs manquants : {', '.join(missing_fields)}")
                    log_message(f"   -> Action requise : Créez les champs '{expected_doi_field}' et '{expected_url_field}' (type Texte) dans Directus.")
                    total_errors += 1
                    continue
                
                log_message(f"   ✅ Champs de retour détectés : DOI='{table_config.doi_field}', URL='{table_config.url_field}'")
                # ---------------------------------------------------------------

                try:
                    url = f"{directus_url}/items/{collection_name}?limit=100"
                    resp = await client.get(url, headers=headers)
                    resp.raise_for_status()
                    items = resp.json().get('data', [])
                    
                    log_message(f"   ✅ {len(items)} éléments trouvés.")
                    
                    if not items:
                        log_message(f"   ⚠️ Rien à synchroniser dans '{collection_name}'.")
                        continue

                    # Déterminer si le filtrage par image est actif
                    must_have_image = (table_config.image1_field or table_config.image2_field)
                    if must_have_image:
                        log_message(f"   🖼️  Filtre actif : Seuls les éléments avec image seront traités.")

                    for i, item in enumerate(items):
                        item_id = item.get('id')
                        if not item_id:
                            continue

                        # --- ÉTAPE 2 : FILTRE PAR IMAGE ---
                        has_image = False
                        
                        if table_config.image1_field:
                            val1 = item.get(table_config.image1_field)
                            if val1: has_image = True
                        
                        if not has_image and table_config.image2_field:
                            val2 = item.get(table_config.image2_field)
                            if val2: has_image = True
                        
                        if must_have_image and not has_image:
                            log_message(f"   ⏭️  Ignoré (Pas d'image) : ID {item_id}")
                            total_skipped += 1
                            continue
                        # ---------------------------------

                        mapping = {
                            "title_field": table_config.title_field,
                            "selected_fields": table_config.selected_fields
                        }
                        metadata = prepare_zenodo_metadata(item, mapping, collection_name)
                        
                        if metadata:
                            log_message(f"   📤 Envoi vers Zenodo : {metadata.get('title', 'Sans titre')}")
                            
                            try:
                                headers_zenodo = {"Authorization": f"Bearer {clean_token}"}
                                data = {'metadata': metadata}
            
                                async with httpx.AsyncClient(timeout=30.0) as zenodo_client:
                                    # 1. Créer le dépôt
                                    res = await zenodo_client.post(
                                        f"{zenodo_url}/api/deposit/depositions", 
                                        json=data, 
                                        headers=headers_zenodo
                                    )
                                    res.raise_for_status()
                                    result = res.json()
                                    
                                    deposition_id = result.get('id')
                                    html_link = result.get('links', {}).get('html', '')
                                    
                                    log_message(f"   ✅ Dépôt créé ! ID: {deposition_id}")
                                    
                                    # 2. Gestion des Images
                                    files_to_process = []
                                    if table_config.image1_field and item.get(table_config.image1_field):
                                        files_to_process.append(item[table_config.image1_field])
                                    if table_config.image2_field and item.get(table_config.image2_field):
                                        files_to_process.append(item[table_config.image2_field])
                                    
                                    for img_ref in files_to_process:
                                        img_url = None
                                        filename = "image.jpg"
                                        
                                        if isinstance(img_ref, str) and img_ref.startswith('http'):
                                            img_url = img_ref
                                            filename = img_ref.split('/')[-1].split('?')[0]
                                        elif isinstance(img_ref, dict) and 'id' in img_ref:
                                            img_url = f"{directus_url}/assets/{img_ref['id']}"
                                            filename = img_ref.get('filename_download', f"{img_ref['id']}.jpg")
                                        elif isinstance(img_ref, str):
                                            img_url = f"{directus_url}/assets/{img_ref}"
                                            filename = f"{img_ref}.jpg"
                                        
                                        if img_url:
                                            try:
                                                async with httpx.AsyncClient(timeout=30.0) as dl_client:
                                                    headers_dl = {"Authorization": f"Bearer {config.directus_token}"}
                                                    resp_img = await dl_client.get(img_url, headers=headers_dl)
                                                    resp_img.raise_for_status()
                                                    
                                                    content_type = resp_img.headers.get('Content-Type', 'image/jpeg')
                                                    
                                                    files_payload = {'file': (filename, resp_img.content, content_type)}
                                                    upload_url = f"{zenodo_url}/api/deposit/depositions/{deposition_id}/files"
                                                    
                                                    async with httpx.AsyncClient(timeout=60.0) as up_client:
                                                        resp_up = await up_client.post(upload_url, files=files_payload, headers=headers_zenodo)
                                                        resp_up.raise_for_status()
                                                        log_message(f"   ✅ Image uploadée : {filename}")
                                            except Exception as img_err:
                                                log_message(f"   ⚠️ Échec upload image : {str(img_err)}")
                                    
                                    # 3. MISE À JOUR DIRECTUS (WRITE-BACK)
                                    doi_to_save = result.get('doi', '') 
                                    if not doi_to_save and deposition_id:
                                        doi_to_save = f"En attente (ID: {deposition_id})"
                                    
                                    if table_config.doi_field or table_config.url_field:
                                        await update_directus_record(
                                            directus_url, 
                                            config.directus_token, 
                                            collection_name, 
                                            str(item_id), 
                                            doi_to_save, 
                                            html_link,
                                            table_config.doi_field,
                                            table_config.url_field
                                        )

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

            log_message(f"🎉 TERMINÉ ! Résumé : {total_success} succès, {total_errors} échecs, {total_skipped} ignorés (filtre).")

    except Exception as e:
        log_message(f"❌ Erreur globale : {str(e)}")
    finally:
        is_running = False

def prepare_zenodo_metadata(item: Dict, mapping: Dict, collection_name: str) -> Dict:
    title_field = mapping.get('title_field')
    
    if not title_field or title_field not in item:
        return None
    
    title = item[title_field]
    desc_parts = []
    
    for field in mapping.get('selected_fields', []):
        if field in item and item[field] is not None:
            val = item[field]
            if isinstance(val, dict):
                val = str(val.get('id', 'Voir détail'))
            desc_parts.append(f"**{field}**: {val}")
    
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
