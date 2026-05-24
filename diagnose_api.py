"""
Script de diagnostic : liste toutes les APIs Synology disponibles
correspondant à SYNO.Foto* et SYNO.FotoTeam*, avec leurs versions et méthodes.
Utile pour trouver le bon namespace/version pour la gestion d'albums.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from config_loader import load_config

config = load_config()
host   = config["synology"]["host"].rstrip("/")
port   = config["synology"]["port"]
base   = f"{host}:{port}"

# 1. Login
print(f"Connexion à {base} …")
r = requests.get(
    f"{base}/photo/webapi/auth.cgi",
    params={
        "api":      "SYNO.API.Auth",
        "version":  3,
        "method":   "login",
        "account":  config["synology"]["username"],
        "passwd":   config["synology"]["password"],
        "format":   "sid",
    },
    verify=False,
    timeout=15,
)
r.raise_for_status()
body = r.json()
if not body.get("success"):
    print("Échec login :", body)
    sys.exit(1)
sid = body["data"]["sid"]
print("Connecté.\n")

# 2. Requête SYNO.API.Info pour tous les namespaces Foto*
r2 = requests.get(
    f"{base}/photo/webapi/entry.cgi",
    params={
        "api":     "SYNO.API.Info",
        "version": 1,
        "method":  "query",
        "query":   "all",
        "_sid":    sid,
    },
    verify=False,
    timeout=15,
)
r2.raise_for_status()
info = r2.json()

if not info.get("success"):
    print("Échec SYNO.API.Info :", info)
    sys.exit(1)

apis = info.get("data", {})

# Sonde les méthodes valides sur les APIs de partage
probe_apis = [
    "SYNO.Foto.Sharing.Passphrase",
    "SYNO.Foto.Sharing.Misc",
    "SYNO.Foto.PublicSharing",
    "SYNO.Foto.Browse.NormalAlbum",
]
methods_to_try = ["list", "get", "set", "create", "delete", "info",
                  "update", "count", "add_item", "share", "publish",
                  "get_passphrase", "generate"]

PHOTO_IDS = [1, 2, 3, 4]  # voonet=1, lou=2, Candice=3, Monique=4

def post_probe(api, method, version=1, **params):
    r = requests.post(
        f"{base}/photo/webapi/entry.cgi",
        data={"api": api, "version": version, "method": method, "_sid": sid, **params},
        verify=False, timeout=10,
    )
    try:
        return r.json()
    except Exception:
        return {"_raw": r.text[:300]}

def post_json(api, method, version=1, **params):
    """Envoie en JSON body (Content-Type: application/json)."""
    r = requests.post(
        f"{base}/photo/webapi/entry.cgi",
        json={"api": api, "version": version, "method": method, "_sid": sid, **params},
        verify=False, timeout=10,
    )
    try:
        return r.json()
    except Exception:
        return {"_raw": r.text[:300]}

# Créer album partagé
print("── Création album ──")
r = post_probe("SYNO.Foto.Browse.NormalAlbum", "create", version=1,
               name="TEST_PERM2", shared="true")
album = r.get("data", {}).get("album", {})
tid, pp = album.get("id"), album.get("passphrase", "")
print(f"  id={tid}, passphrase={pp}")

# 1. JSON body — permission avec vrais types Python (pas des strings)
print("\n── Passphrase.update via JSON body ──")
json_combos = [
    {"permission": PHOTO_IDS},
    {"permission": [{"id": i, "role": "view"} for i in PHOTO_IDS]},
    {"permission": [{"user_id": i, "permission": 0} for i in PHOTO_IDS]},
    {"permission": True, "member": PHOTO_IDS},
    {"permission": 0, "member": PHOTO_IDS},
    {"member": [{"id": i, "role": "view"} for i in PHOTO_IDS]},
    {"member": [{"user_id": i, "type": "view"} for i in PHOTO_IDS]},
]
for kw in json_combos:
    r = post_json("SYNO.Foto.Sharing.Passphrase", "update", passphrase=pp, **kw)
    code = r.get("error", {}).get("code") if not r.get("success") else "OK"
    print(f"  {str(kw)[:70]:<72} → {code}  {r.get('error','') if code != 'OK' else ''}")
    if code == "OK":
        r2 = post_probe("SYNO.Foto.Sharing.Passphrase", "get", passphrase=pp)
        print(f"    get → {r2}")

# Nettoyage
post_probe("SYNO.Foto.Browse.NormalAlbum", "delete", version=1, id=f"[{tid}]")
print(f"\nAlbum {tid} supprimé.")

# 3. Logout
requests.get(
    f"{base}/photo/webapi/auth.cgi",
    params={"api": "SYNO.API.Auth", "version": 3, "method": "logout", "_sid": sid},
    verify=False, timeout=10,
)
print("\nDéconnecté.")
