import os
import asyncio
import json
import re
from datetime import datetime, timezone
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

# --- NOUVELLE FONCTION UTILITAIRE ---
def get_nested_value(data: dict, field_path: str):
    """
    Lit une valeur dans un dictionnaire, même si elle est imbriquée via une relation.
    Ex: field_path = 'relation.champ' -> retourne data['relation']['champ']
    """
    if not field_path or not data:
        return None
    
    # Si pas de point, c'est un accès direct
    if '.' not in field_path:
        return data.get(field_path)
    
    keys = field_path.split('.')
    current = data
    
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current

# --- Modèles de Données ---

class LinkedFieldConfig(BaseModel):
    """Configuration d'un champ lié (Relation -> Champ cible)"""
    relationField: str
    targetCollection: str
    targetField: str

class TableConfig(BaseModel):
    """Configuration spécifique pour une seule table"""
    name: str
    title_field: str
    selected_fields: List[str]
    image1_field: Optional[str] = None
    image2_field: Optional[str] = None
    doi_field: Optional[str] = None
    url_field: Optional[str] = None
    linked_fields: List[LinkedFieldConfig] = []

class SyncConfig(BaseModel):
    """Configuration globale de synchronisation"""
    directus_url: str
    directus_token: str
    zenodo_url: str
    zenodo_token: str
    collections: List[TableConfig]
    publish: bool = False

class ZenodoConnectionRequest(BaseModel):
    zenodo_url: str
    zenodo_token: str

# --- Gestion du Cycle de Vie ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    log_message("🚀 Démarrage du serveur Sanctuaire Sync (Production Ready)...")
    yield
    log_message("🛑 Arrêt du serveur.")

app = FastAPI(lifespan=lifespan, title="Sanctuaire Sync API")

# --- Répertoire des profils ---
CONFIGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "configs")

def _safe_profile_name(name: str) -> str:
    """Sanitize profile name to prevent path traversal."""
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Nom de profil vide")
    if not re.match(r'^[\w\s\-]{1,50}$', name.strip()):
        raise HTTPException(status_code=400, detail="Nom invalide (lettres, chiffres, tirets, max 50 car.)")
    safe = re.sub(r'\s+', '_', name.strip())
    safe = re.sub(r'[^\w\-]', '', safe)
    if not safe:
        raise HTTPException(status_code=400, detail="Nom de profil invalide après nettoyage")
    return safe

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
    paths_to_try = [
        os.path.join(os.path.dirname(__file__), "index.html"),
        os.path.join(os.path.dirname(__file__), "static", "index.html"),
        "index.html"
    ]
    for file_path in paths_to_try:
        if os.path.exists(file_path):
            return FileResponse(file_path)
    
    return {"status": "API Running", "message": "Interface non trouvée, mais le backend est actif."}

@app.get("/api/logs")
async def get_logs():
    return {"logs": log_buffer, "running": is_running}

@app.post("/api/test-zenodo")
async def test_zenodo(req: ZenodoConnectionRequest):
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"{req.zenodo_url.rstrip('/')}/api/deposit/depositions?size=1",
                headers={"Authorization": f"Bearer {req.zenodo_token.strip()}"}
            )
            return {"connected": resp.status_code == 200}
    except Exception:
        return {"connected": False}

@app.get("/api/profiles")
async def list_profiles():
    os.makedirs(CONFIGS_DIR, exist_ok=True)
    profiles = sorted([
        f[:-5] for f in os.listdir(CONFIGS_DIR)
        if f.endswith('.json') and not f.startswith('_')
    ])
    active = ""
    active_file = os.path.join(CONFIGS_DIR, "_active.txt")
    if os.path.exists(active_file):
        with open(active_file, 'r', encoding='utf-8') as f:
            active = f.read().strip()
    if active and active not in profiles:
        active = ""
    return {"profiles": profiles, "active": active}

@app.get("/api/profiles/{name}")
async def get_profile(name: str):
    safe = _safe_profile_name(name)
    path = os.path.join(CONFIGS_DIR, f"{safe}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Profil introuvable")
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    with open(os.path.join(CONFIGS_DIR, "_active.txt"), 'w', encoding='utf-8') as f:
        f.write(safe)
    return data

@app.post("/api/profiles/{name}")
async def save_profile(name: str, request: Request):
    os.makedirs(CONFIGS_DIR, exist_ok=True)
    safe = _safe_profile_name(name)
    data = await request.json()
    path = os.path.join(CONFIGS_DIR, f"{safe}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    with open(os.path.join(CONFIGS_DIR, "_active.txt"), 'w', encoding='utf-8') as f:
        f.write(safe)
    return {"saved": True, "name": safe}

@app.delete("/api/profiles/{name}")
async def delete_profile(name: str):
    safe = _safe_profile_name(name)
    path = os.path.join(CONFIGS_DIR, f"{safe}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Profil introuvable")
    os.remove(path)
    active_file = os.path.join(CONFIGS_DIR, "_active.txt")
    if os.path.exists(active_file):
        with open(active_file, 'r', encoding='utf-8') as f:
            active = f.read().strip()
        if active == safe:
            os.remove(active_file)
    return {"deleted": True}

@app.post("/api/clean-zenodo")
async def clean_zenodo(req: ZenodoConnectionRequest):
    deleted = 0
    errors = 0
    skipped = 0
    base_url = req.zenodo_url.rstrip("/")
    h = {"Authorization": f"Bearer {req.zenodo_token.strip()}"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            page = 1
            while page <= 10:
                resp = await client.get(
                    f"{base_url}/api/deposit/depositions",
                    params={"size": 100, "page": page},
                    headers=h
                )
                if resp.status_code != 200:
                    break
                depositions = resp.json()
                if not depositions:
                    break
                for dep in depositions:
                    dep_id = dep.get('id')
                    state = dep.get('state', '')
                    if not dep_id:
                        continue
                    # Uniquement les brouillons (non publiés)
                    if state not in ('unsubmitted', 'inprogress'):
                        skipped += 1
                        continue
                    try:
                        del_resp = await client.delete(
                            f"{base_url}/api/deposit/depositions/{dep_id}",
                            headers=h
                        )
                        if del_resp.status_code == 204:
                            deleted += 1
                        else:
                            errors += 1
                    except Exception:
                        errors += 1
                if len(depositions) < 100:
                    break
                page += 1
        log_message(f"🧹 Nettoyage Zenodo : {deleted} supprimés, {errors} erreurs, {skipped} ignorés (publiés)")
        return {"deleted": deleted, "errors": errors, "skipped": skipped}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            from starlette.responses import Response as StarletteResponse

            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=clean_headers,
                content=body,
                params=request.query_params
            )
            
            # Les réponses 304/204/1xx n'ont pas de corps — retourner sans body
            no_body_statuses = {204, 304}
            if resp.status_code in no_body_statuses or (100 <= resp.status_code < 200):
                return StarletteResponse(status_code=resp.status_code)
            
            return JSONResponse(
                status_code=resp.status_code,
                content=resp.json() if resp.content else {},
                headers={k: v for k, v in resp.headers.items() if k.lower() not in ["content-length", "content-encoding", "transfer-encoding"]}
            )
        except httpx.ConnectError:
            log_message(f"❌ Impossible de se connecter à {target_base_url}", "ERROR")
            raise HTTPException(status_code=503, detail=f"Impossible de joindre Directus")
        except Exception as e:
            log_message(f"❌ Erreur Proxy: {str(e)}", "ERROR")
            raise HTTPException(status_code=500, detail=str(e))

# --- Logique de Synchronisation ---

@app.post("/api/start-sync")
async def start_sync(config: SyncConfig, background_tasks: BackgroundTasks):
    global is_running
    if is_running:
        raise HTTPException(status_code=400, detail="Une synchronisation est déjà en cours.")
    
    log_buffer.clear()
    log_message("🆕 Nouvelle session de synchronisation démarrée")
    log_message(f"📋 Tables à traiter : {[c.name for c in config.collections]}")
    
    is_running = True
    background_tasks.add_task(run_sync_process, config)
    return {"status": "started", "message": "Synchronisation lancée en arrière-plan"}

async def update_directus_record(directus_url: str, token: str, collection: str, item_id: str, doi: str, url: str, doi_field: Optional[str], url_field: Optional[str]):
    """Met à jour l'élément Directus avec le DOI et l'URL reçus de Zenodo"""
    if not doi_field and not url_field:
        return

    payload = {}
    if doi_field and doi:
        payload[doi_field] = doi
    if url_field and url:
        payload[url_field] = url
        
    try:
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
            log_message(f"   ✅ Directus mis à jour (DOI: {doi if doi else 'N/A'})")
    except Exception as e:
        log_message(f"   ⚠️ Échec mise à jour Directus : {str(e)}", "WARNING")

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
                log_message(f"📂 Traitement de la table : {collection_name}")
                
                # --- ÉTAPE 1 : VÉRIFICATION DES CHAMPS DE RETOUR ---
                url_fields_check = f"{directus_url}/fields/{collection_name}"
                resp_fields = await client.get(url_fields_check, headers=headers)
                
                existing_fields = []
                if resp_fields.status_code == 200:
                    fields_data = resp_fields.json().get('data', [])
                    existing_fields = [f['field'] for f in fields_data]
                
                if "zenodo_doi" in existing_fields:
                    table_config.doi_field = "zenodo_doi"
                    log_message(f"   ✅ Champ DOI détecté")
                else:
                    table_config.doi_field = None
                    log_message(f"   ℹ️  Champ DOI absent (aucun retour)")
                    
                if "zenodo_record_url" in existing_fields:
                    table_config.url_field = "zenodo_record_url"
                    log_message(f"   ✅ Champ URL détecté")
                else:
                    table_config.url_field = None
                    log_message(f"   ℹ️  Champ URL absent (aucun retour)")

                try:
                    # --- ÉTAPE 2 : CONSTRUCTION DE LA REQUÊTE ---
                    # Champs racine explicites (remplace le wildcard * qui cause des 403)
                    root_fields = ["id"]
                    for f in list(table_config.selected_fields):
                        if f and '.' not in f and f not in root_fields:
                            root_fields.append(f)
                    # Title fields (peuvent être pipe-séparés)
                    for tf in (table_config.title_field or '').split('|'):
                        tf = tf.strip()
                        if tf and '.' not in tf and tf not in root_fields:
                            root_fields.append(tf)
                    # Champs de retour DOI/URL
                    if table_config.doi_field and table_config.doi_field not in root_fields:
                        root_fields.append(table_config.doi_field)
                    if table_config.url_field and table_config.url_field not in root_fields:
                        root_fields.append(table_config.url_field)

                    deep_fields = []
                    if table_config.linked_fields:
                        log_message(f"   🔗 Configuration Deep Fetching ({len(table_config.linked_fields)} relations)...")
                        for link in table_config.linked_fields:
                            deep_field = f"{link.relationField}.{link.targetField}"
                            deep_fields.append(deep_field)
                            log_message(f"      -> Demande: {deep_field}")
                    
                    # Champs images : racine ou imbriqués
                    for img_field in [table_config.image1_field, table_config.image2_field]:
                        if not img_field:
                            continue
                        if '.' in img_field:
                            if img_field not in deep_fields:
                                deep_fields.append(img_field)
                                log_message(f"      -> Image imbriquée ajoutée: {img_field}")
                        else:
                            if img_field not in root_fields:
                                root_fields.append(img_field)
                    
                    fields_param = ",".join(root_fields + deep_fields)
                    log_message(f"   📡 Requête API ({len(root_fields)} champs racine + {len(deep_fields)} liés)")
                    
                    url = f"{directus_url}/items/{collection_name}?limit=100&fields={fields_param}"
                    
                    resp = await client.get(url, headers=headers)
                    
                    # Fallback si 403 : réessayer sans les champs à 3+ niveaux de profondeur
                    if resp.status_code == 403:
                        ultra_deep = [f for f in deep_fields if f.count('.') > 1]
                        if ultra_deep:
                            shallow_deep = [f for f in deep_fields if f.count('.') <= 1]
                            log_message(f"   ⚠️ Requête refusée (403), {len(ultra_deep)} champs profonds exclus, nouvelle tentative...", "WARNING")
                            fields_param_simple = ",".join(root_fields + shallow_deep)
                            url = f"{directus_url}/items/{collection_name}?limit=100&fields={fields_param_simple}"
                            resp = await client.get(url, headers=headers)
                    
                    resp.raise_for_status()
                    items = resp.json().get('data', [])
                    
                    log_message(f"   ✅ {len(items)} éléments récupérés.")
                    
                    if not items:
                        log_message(f"   ⚠️  Rien à synchroniser.")
                        continue

                    must_have_image = (table_config.image1_field or table_config.image2_field)

                    for i, item in enumerate(items):
                        item_id = item.get('id')
                        if not item_id: continue

                        # --- SKIP si DOI déjà présent ---
                        if table_config.doi_field and item.get(table_config.doi_field):
                            log_message(f"   ⏭️  SKIP ID {item_id} : DOI déjà présent ({item.get(table_config.doi_field)})")
                            total_skipped += 1
                            continue

                        # --- FILTRE IMAGE CORRIGÉ ---
                        has_image = False
                        
                        # Utilisation de get_nested_value pour lire les relations
                        val_img1 = get_nested_value(item, table_config.image1_field) if table_config.image1_field else None
                        val_img2 = get_nested_value(item, table_config.image2_field) if table_config.image2_field else None

                        if val_img1: has_image = True
                        if val_img2: has_image = True
                        
                        if must_have_image and not has_image:
                            log_message(f"   ⏭️  SKIP ID {item_id} : Aucune image. (Check1: {table_config.image1_field}={bool(val_img1)}, Check2: {table_config.image2_field}={bool(val_img2)})", "WARNING")
                            total_skipped += 1
                            continue
                        # --- FIN FILTRE IMAGE ---

                        mapping = {
                            "title_field": table_config.title_field,
                            "selected_fields": table_config.selected_fields,
                            "linked_fields": table_config.linked_fields
                        }
                        metadata = prepare_zenodo_metadata(item, mapping, collection_name)
                        
                        if metadata:
                            log_message(f"   📤 Envoi : {metadata.get('title', 'Sans titre')}")
                            
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
                                    log_message(f"   ✅ Dépôt créé (ID: {deposition_id})")
                                    
                                    # 2. Gestion des Images (Sécurisée et Corrigée)
                                    files_to_process = []
                                    
                                    # Récupération sécurisée des références d'images
                                    if table_config.image1_field:
                                        val = get_nested_value(item, table_config.image1_field)
                                        if val: files_to_process.append(val)
                                    if table_config.image2_field:
                                        val = get_nested_value(item, table_config.image2_field)
                                        if val: files_to_process.append(val)
                                    
                                    for img_ref in files_to_process:
                                        img_url = None
                                        filename = "image.jpg"
                                        
                                        # Résolution de l'URL selon le type de donnée
                                        if isinstance(img_ref, str) and img_ref.startswith('http'):
                                            img_url = img_ref
                                            filename = img_ref.split('/')[-1].split('?')[0] or "image.jpg"
                                        elif isinstance(img_ref, dict) and 'id' in img_ref:
                                            img_url = f"{directus_url}/assets/{img_ref['id']}"
                                            filename = img_ref.get('filename_download', f"{img_ref['id']}.jpg")
                                        elif isinstance(img_ref, str): # UUID seul
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
                                                log_message(f"   ⚠️  Échec upload image : {str(img_err)}", "WARNING")
                                    
                                    # 3. GÉNÉRATION ET UPLOAD DU FICHIER DE PREUVE
                                    timestamp_utc = datetime.now(timezone.utc).isoformat()
                                    proof_lines = [
                                        "=== PREUVE D'ANTERIORITE - Sanctuaire Non-OGM ===",
                                        f"Date et heure UTC : {timestamp_utc}",
                                        f"Collection        : {collection_name}",
                                        f"ID Directus       : {item_id}",
                                        f"Titre             : {metadata.get('title', 'N/A')}",
                                        "",
                                        "--- Données synchronisées ---",
                                    ]
                                    for field in table_config.selected_fields:
                                        val = get_nested_value(item, field)
                                        if val is not None:
                                            proof_lines.append(f"{field}: {val}")
                                    for link in table_config.linked_fields:
                                        full_path = f"{link.relationField}.{link.targetField}"
                                        val = get_nested_value(item, full_path)
                                        if val:
                                            proof_lines.append(f"{link.relationField} > {link.targetField}: {val}")
                                    proof_lines.append("")
                                    proof_lines.append("Ce document constitue une preuve d'antériorité horodatée par le CERN (Zenodo).")
                                    proof_content = "\n".join(proof_lines).encode('utf-8')
                                    proof_filename = f"preuve_{collection_name}_{item_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
                                    
                                    try:
                                        proof_upload_url = f"{zenodo_url}/api/deposit/depositions/{deposition_id}/files"
                                        async with httpx.AsyncClient(timeout=30.0) as proof_client:
                                            resp_proof = await proof_client.post(
                                                proof_upload_url,
                                                files={'file': (proof_filename, proof_content, 'text/plain')},
                                                headers=headers_zenodo
                                            )
                                            resp_proof.raise_for_status()
                                            log_message(f"   ✅ Fichier de preuve uploadé : {proof_filename}")
                                    except Exception as proof_err:
                                        log_message(f"   ⚠️  Échec upload preuve : {str(proof_err)}", "WARNING")

                                    # 4. PUBLICATION (si demandée)
                                    doi_to_save = result.get('doi', '')
                                    if not doi_to_save and deposition_id:
                                        doi_to_save = f"Brouillon (ID: {deposition_id})"

                                    if config.publish:
                                        try:
                                            pub_resp = await zenodo_client.post(
                                                f"{zenodo_url}/api/deposit/depositions/{deposition_id}/actions/publish",
                                                headers=headers_zenodo
                                            )
                                            if pub_resp.status_code == 202:
                                                pub_result = pub_resp.json()
                                                doi_to_save = pub_result.get('doi', doi_to_save)
                                                html_link = pub_result.get('links', {}).get('html', html_link)
                                                log_message(f"   ✅ PUBLIÉ ! DOI officiel: {doi_to_save}")
                                            else:
                                                log_message(f"   ⚠️ Échec publication: {pub_resp.status_code}", "WARNING")
                                        except Exception as pub_err:
                                            log_message(f"   ⚠️ Erreur publication: {str(pub_err)}", "WARNING")
                                    else:
                                        log_message(f"   📝 Dépôt en brouillon (ID: {deposition_id})")

                                    # 5. MISE À JOUR DIRECTUS
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
                                log_message(f"   ❌ Erreur Zenodo : {str(zenodo_err)}", "ERROR")
                                total_errors += 1
                        else:
                            log_message(f"   ⚠️  Élément ignoré (titre manquant).")
                            total_errors += 1
                            
                except Exception as e:
                    log_message(f"   ❌ Erreur critique sur '{collection_name}': {str(e)}", "ERROR")
                    total_errors += 1

            log_message(f"🏁 TERMINÉ ! Succès: {total_success} | Échecs: {total_errors} | Ignorés: {total_skipped}")

    except Exception as e:
        log_message(f"❌ Erreur globale : {str(e)}", "ERROR")
    finally:
        is_running = False

def prepare_zenodo_metadata(item: Dict, mapping: Dict, collection_name: str) -> Dict:
    title_field = mapping.get('title_field')
    
    # Support multi-champs titre (séparés par |)
    title_parts = []
    if title_field:
        for tf in title_field.split('|'):
            tf = tf.strip()
            if tf:
                val = get_nested_value(item, tf)
                if val is not None:
                    title_parts.append(str(val))
    
    title = " - ".join(title_parts) if title_parts else None
    
    if not title:
        return None
    
    desc_parts = []
    
    # Champs standards
    for field in mapping.get('selected_fields', []):
        val = get_nested_value(item, field)
        if val is not None:
            if isinstance(val, dict):
                val = str(val.get('id', 'Voir détail'))
            desc_parts.append(f"**{field}**: {val}")
    
    # Champs liés
    linked_fields_config = mapping.get('linked_fields', [])
    for link in linked_fields_config:
        rel_field = link.relationField
        target_field = link.targetField
        
        # On reconstruit le chemin complet pour la valeur
        full_path = f"{rel_field}.{target_field}"
        val = get_nested_value(item, full_path)
        
        if val:
            desc_parts.append(f"**{rel_field} > {target_field}**: {val}")

    desc_parts.append(f"**Source**: Table '{collection_name}' (Sanctuaire Non-OGM)")
    
    return {
        "title": f"[{collection_name}] {title}",
        "description": "\n".join(desc_parts) if desc_parts else "Données synchronisées",
        "upload_type": "dataset",
        "access_right": "open",
        "license": "cc-by-4.0",
        "creators": [{"name": "Sanctuaire Non-OGM"}]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)