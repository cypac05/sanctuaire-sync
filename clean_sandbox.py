import httpx
import time
import sys

# CONFIGURATION
ZENODO_SANDBOX_URL = "https://sandbox.zenodo.org"
ACCESS_TOKEN = "put the token here"  # <--- REMPLACEZ CECI PAR VOTRE TOKEN

def clean_all_depositions():
    print(f"🧹 Nettoyage complet de {ZENODO_SANDBOX_URL}...")
    
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    all_deleted = 0
    errors = 0
    
    with httpx.Client(timeout=30.0) as client:
        page = 1
        per_page = 100  # Maximum autorisé par Zenodo
        
        while True:
            print(f"\n📄 Récupération de la page {page}...")
            resp = client.get(
                f"{ZENODO_SANDBOX_URL}/api/deposit/depositions", 
                headers=headers, 
                params={"page": page, "size": per_page}
            )
            
            if resp.status_code != 200:
                print(f"❌ Erreur API : {resp.status_code}")
                break
                
            depositions = resp.json()
            
            if not depositions:
                print("✅ Plus aucun dépôt trouvé.")
                break
            
            print(f"   -> {len(depositions)} dépôts trouvés sur cette page.")
            
            for dep in depositions:
                dep_id = dep.get('id')
                dep_title = dep.get('metadata', {}).get('title', 'Sans titre')[:40] # Tronquer le titre
                
                try:
                    # Tentative de suppression directe
                    delete_resp = client.delete(
                        f"{ZENODO_SANDBOX_URL}/api/deposit/depositions/{dep_id}", 
                        headers=headers
                    )
                    
                    if delete_resp.status_code == 204:
                        print(f"   ✅ Supprimé : [{dep_id}] {dep_title}...")
                        all_deleted += 1
                    elif delete_resp.status_code == 403:
                        # Parfois besoin de passer en brouillon d'abord si publié (rare sur Sandbox)
                        print(f"   ⚠️  [{dep_id}] Verrouillé, tentative de dépublication...")
                        client.post(f"{ZENODO_SANDBOX_URL}/api/deposit/depositions/{dep_id}/actions/draft", headers=headers)
                        time.sleep(0.5)
                        # Réessayer la suppression
                        delete_resp2 = client.delete(f"{ZENODO_SANDBOX_URL}/api/deposit/depositions/{dep_id}", headers=headers)
                        if delete_resp2.status_code == 204:
                            print(f"   ✅ Supprimé (après dépublication) : [{dep_id}]")
                            all_deleted += 1
                        else:
                            print(f"   ❌ Échec définitif : [{dep_id}]")
                            errors += 1
                    else:
                        print(f"   ❌ Échec [{dep_id}] : Code {delete_resp.status_code}")
                        errors += 1
                        
                except Exception as e:
                    print(f"   ❌ Exception [{dep_id}] : {str(e)}")
                    errors += 1
                
                # Petite pause pour ne pas saturer l'API
                time.sleep(0.2)

            page += 1
            # Sécurité : on arrête après 10 pages si ça boucle (au cas où)
            if page > 10: 
                print("⚠️  Limite de pages atteinte (10), arrêt pour sécurité.")
                break

    print("\n" + "="*40)
    print(f"🏁 TERMINÉ !")
    print(f"   Total supprimé : {all_deleted}")
    print(f"   Erreurs/Ignorés : {errors}")
    print("="*40)

if __name__ == "__main__":
    if ACCESS_TOKEN == "VOTRE_TOKEN_SANDBOX_ICI":
        print("❌ ERREUR : Modifiez le script pour mettre votre vrai token !")
        sys.exit(1)
    
    confirm = input(f"\n⚠️  ATTENTION : Cela va effacer TOUS les dépôts accessibles par ce token.\nTapez 'oui' pour confirmer : ")
    if confirm.lower() == "oui":
        clean_all_depositions()
    else:
        print("Annulé.")
