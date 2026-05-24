"""
Client HTTP pour l'API Synology Photos — espace partagé (SYNO.FotoTeam.*).

Résolution automatique de QuickConnect : si config.yml contient une URL
*.quickconnect.to, le client interroge l'API Synology pour trouver la vraie
adresse du NAS (réseau local en priorité, relai en dernier recours).

Toutes les opérations d'écriture (create_album, add_items_to_album, share_album,
delete_album) sont bloquées en mode dry_run=True (valeur par défaut).
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import logging
import re
import struct
import time
from typing import Any, Optional

import requests
import urllib3
from requests.exceptions import ConnectionError as ReqConnError
from requests.exceptions import Timeout as ReqTimeout

# Supprime les warnings SSL pour les connexions locales sans certificat valide
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger("album")

# ── Constantes ────────────────────────────────────────────────────────────────
_AUTH_CGI       = "/photo/webapi/auth.cgi"
_ENTRY_CGI      = "/photo/webapi/entry.cgi"
_QC_API         = "https://global.quickconnect.to/Serv.php"
_TIMEOUT        = 30   # secondes pour les appels API normaux
_PROBE_TIMEOUT  = 4    # secondes pour tester si une IP locale répond
_RETRIES        = 3    # tentatives max sur erreur réseau
_BATCH          = 100  # photos max par appel add_item

_ERR = {
    101: "paramètre invalide",
    102: "API introuvable (vérifiez le namespace SYNO.FotoTeam.*)",
    105: "permission refusée",
    106: "session expirée",
    107: "session invalide",
    119: "identifiants ou code OTP incorrect",
    400: "login ou mot de passe incorrect",
    401: "compte désactivé",
    402: "permission refusée",
    403: "2FA activée sur ce compte — otp_secret requis dans config.yml (ou créer un compte sans 2FA)",
    404: "code OTP incorrect",
    406: "2FA obligatoire sur ce compte",
    800: "compte introuvable dans Synology Photos",
    801: "accès à l'espace partagé refusé — accorde les droits dans Synology Photos > Paramètres > Espace partagé > Autorisations",
}
_AUTH_CODES = {105, 106, 107, 119}


# ── Exceptions ────────────────────────────────────────────────────────────────
class AuthenticationError(Exception):
    """Identifiants incorrects, permission refusée ou session expirée."""


class SynologyAPIError(Exception):
    """Erreur retournée par l'API Synology (hors authentification)."""


# ── TOTP minimal (2FA sans dépendance externe) ────────────────────────────────
def _totp(secret: str) -> str:
    """Génère un code TOTP 6 chiffres depuis un secret base32 (RFC 6238)."""
    key     = base64.b32decode(secret.upper().replace(" ", ""))
    counter = struct.pack(">Q", int(time.time()) // 30)
    mac     = hmac.new(key, counter, digestmod=hashlib.sha1).digest()
    offset  = mac[-1] & 0x0F
    value   = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFF_FFFF
    return f"{value % 1_000_000:06d}"


# ── Résolution d'adresse ──────────────────────────────────────────────────────
def _resolve_connection(host: str, port: int) -> tuple[str, bool]:
    """
    Détermine l'URL de base réelle du NAS et si SSL doit être vérifié.
    Retourne (base_url, verify_ssl).

    Trois cas :
    - localhost / IP privée directe → utilise telle quelle, verify=False
    - *.quickconnect.to             → interroge l'API QuickConnect
    - autre FQDN                    → utilise telle quelle, verify=True
    """
    # Cas 1 : IP directe ou localhost (ex: http://192.168.1.50 ou http://127.0.0.1)
    if re.match(r"https?://(localhost|127\.|10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.)", host):
        base = f"{host.rstrip('/')}:{port}"
        log.debug("Connexion directe (locale) : %s", base)
        return base, False

    # Cas 2 : URL QuickConnect
    m = re.match(r"https?://([^/]+)\.quickconnect\.to", host, re.IGNORECASE)
    if m:
        qc_id = m.group(1)
        return _resolve_quickconnect(qc_id, port)

    # Cas 3 : FQDN ordinaire
    base = f"{host.rstrip('/')}:{port}"
    log.debug("Connexion FQDN : %s", base)
    return base, True


def _resolve_quickconnect(qc_id: str, preferred_https_port: int) -> tuple[str, bool]:
    """
    Interroge l'API QuickConnect pour trouver la meilleure route vers le NAS.
    Essaie dans l'ordre : LAN (HTTP) → relai HTTPS → IP externe HTTPS.
    Retourne (base_url, verify_ssl).
    """
    log.info("Résolution QuickConnect de '%s'…", qc_id)

    # L'API QuickConnect attend un POST avec un corps JSON (pas un GET)
    body = {
        "version":           "1",
        "command":           "get_server_info",
        "stop_when_error":   "false",
        "stop_when_success": "false",
        "id":                "dsm_portal_https",
        "serverID":          qc_id,
        "is_gofile":         False,
    }
    try:
        resp = requests.post(_QC_API, json=body, timeout=10, verify=True)
        resp.raise_for_status()
        if not resp.text.strip():
            raise ValueError("Réponse vide — l'API QuickConnect n'a rien renvoyé.")
        data = resp.json()
    except Exception as exc:
        log.error("Échec résolution QuickConnect (réponse brute: %r)", getattr(exc, "response", None) and exc.response.text[:200] if hasattr(exc, "response") else "")  # type: ignore[union-attr]
        raise ConnectionError(
            f"Impossible de résoudre QuickConnect '{qc_id}' : {exc}\n"
            "→ Solution rapide : remplace dans config.yml\n"
            "    host: \"http://192.168.X.X\"   (l'IP locale de ton NAS)\n"
            "    port: 5000\n"
            "  Tu trouves l'IP dans DSM > Panneau de configuration > Réseau."
        ) from exc

    if not data.get("success"):
        raise ConnectionError(f"QuickConnect a retourné une erreur pour '{qc_id}'.")

    server  = data.get("server", {})
    service = server.get("service", {})
    http_port  = int(service.get("port",       5000))
    https_port = int(service.get("https_port", preferred_https_port))

    # ── Essai 1 : IPs LAN (HTTP, pas de cert) ────────────────────────────────
    for iface in server.get("interface", []):
        ip = iface.get("ip", "").strip()
        if not ip or ip in ("0.0.0.0", "") or ip.startswith("169."):
            continue
        candidate = f"http://{ip}:{http_port}"
        log.debug("Test LAN : %s …", candidate)
        try:
            r = requests.get(
                f"{candidate}/photo/webapi/auth.cgi",
                params={"api": "SYNO.API.Info", "version": "1", "method": "query"},
                timeout=_PROBE_TIMEOUT,
                verify=False,
            )
            if r.status_code < 500:
                log.info("NAS joignable en local : %s", candidate)
                return candidate, False
        except Exception as exc:
            log.debug("  ↳ non joignable (%s)", exc)

    # ── Essai 2 : relai QuickConnect (HTTPS) ─────────────────────────────────
    relay_ip   = service.get("relay_ip",   "")
    relay_port = service.get("relay_port", 0)
    if relay_ip and relay_port:
        candidate = f"https://{relay_ip}:{relay_port}"
        log.info("Utilisation du relai QuickConnect : %s", candidate)
        return candidate, True

    # ── Essai 3 : IP externe (HTTPS) ─────────────────────────────────────────
    ext_ip = server.get("external", {}).get("ip", "")
    if ext_ip:
        candidate = f"https://{ext_ip}:{https_port}"
        log.info("Utilisation de l'IP externe : %s", candidate)
        return candidate, True

    raise ConnectionError(
        f"Aucune route trouvée vers le NAS '{qc_id}'.\n"
        "Conseil : note l'IP locale du NAS (depuis DSM > Panneau de configuration >\n"
        "Réseau) et remplace l'URL dans config.yml par ex: http://192.168.1.50"
    )


# ── Client principal ──────────────────────────────────────────────────────────
class SynologyPhotosClient:
    """
    Client pour l'API Synology Photos (espace partagé).

    Usage recommandé :
        with SynologyPhotosClient(config, dry_run=True) as client:
            total = client.count_items()
    """

    def __init__(self, config: dict[str, Any], dry_run: bool = True) -> None:
        syno = config["synology"]
        self._config_host = syno["host"].rstrip("/")
        self._config_port = int(syno["port"])
        self._user        = syno["username"]
        self._passwd      = syno["password"]
        self._otp_sec: Optional[str] = syno.get("otp_secret")
        self.dry_run      = dry_run
        self._sid: Optional[str] = None
        self._base: Optional[str] = None        # résolu au premier login
        self._verify_ssl: bool    = True        # mis à jour par _resolve_connection
        self._http = requests.Session()

        if dry_run:
            log.info("Mode DRY-RUN activé — aucune modification ne sera faite sur le NAS")

    # ── Authentification ──────────────────────────────────────────────────────

    def login(self) -> None:
        """
        Ouvre une session Synology.
        Résout automatiquement l'adresse du NAS (QuickConnect, LAN ou FQDN).
        Lève AuthenticationError si les identifiants sont incorrects.
        """
        # Résolution de l'URL (une seule fois par instance)
        if self._base is None:
            self._base, self._verify_ssl = _resolve_connection(
                self._config_host, self._config_port
            )

        params: dict[str, Any] = {
            "api":               "SYNO.API.Auth",
            "version":           3,
            "method":            "login",
            "account":           self._user,
            "passwd":            self._passwd,
            "enable_syno_token": "no",
        }
        if self._otp_sec:
            params["otp_code"] = _totp(self._otp_sec)
            log.debug("2FA activée — code TOTP généré")

        log.debug("AUTH login → %s", self._base + _AUTH_CGI)
        resp = self._get(_AUTH_CGI, params)

        if not resp.get("success"):
            code = resp.get("error", {}).get("code", 0)
            raise AuthenticationError(f"Connexion impossible : {_ERR.get(code, f'code {code}')}")

        self._sid = resp["data"]["sid"]
        log.info("Connecté au NAS (compte : %s, url : %s)", self._user, self._base)

    def logout(self) -> None:
        """Ferme la session proprement (sans lever d'exception)."""
        if not self._sid:
            return
        log.debug("AUTH logout")
        try:
            self._get(_AUTH_CGI, {
                "api": "SYNO.API.Auth", "version": 3,
                "method": "logout", "_sid": self._sid,
            })
        except Exception:
            pass
        finally:
            self._sid = None
        log.info("Session fermée")

    # ── Couche HTTP ───────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict) -> dict:
        """GET avec retry exponentiel sur erreurs réseau (3 tentatives max)."""
        url   = (self._base or "") + path
        delay = 1.0
        last_exc: Exception = RuntimeError("unreachable")
        for attempt in range(1, _RETRIES + 1):
            try:
                r = self._http.get(
                    url, params=params,
                    timeout=_TIMEOUT,
                    verify=self._verify_ssl,
                )
                r.raise_for_status()
                return r.json()
            except (ReqConnError, ReqTimeout) as exc:
                last_exc = exc
                if attempt == _RETRIES:
                    break
                log.warning(
                    "Erreur réseau (tentative %d/%d) : %s — nouvel essai dans %ds",
                    attempt, _RETRIES, exc, int(delay),
                )
                time.sleep(delay)
                delay *= 2
        raise last_exc

    def _api(self, api: str, method: str, version: int = 1, **kw: Any) -> dict:
        """
        Appel authentifié à entry.cgi.
        Gère automatiquement l'expiration de session (re-login + 1 retry).
        Ne retente PAS sur erreur d'authentification.
        """
        if not self._sid:
            raise AuthenticationError("Non connecté — appelez login() d'abord.")

        payload = {"api": api, "version": version, "method": method, "_sid": self._sid, **kw}
        log.debug("→ %s.%s  %s", api, method,
                  json.dumps({k: v for k, v in kw.items()}, ensure_ascii=False, default=str))

        resp = self._get(_ENTRY_CGI, payload)

        if resp.get("success"):
            return resp.get("data") or {}

        code = resp.get("error", {}).get("code", 0)

        # Session expirée → re-login unique
        if code == 106:
            log.warning("Session expirée, reconnexion automatique…")
            self.login()
            payload["_sid"] = self._sid
            resp = self._get(_ENTRY_CGI, payload)
            if resp.get("success"):
                return resp.get("data") or {}
            code = resp.get("error", {}).get("code", 0)

        msg = _ERR.get(code, f"code {code}")
        if code in _AUTH_CODES:
            raise AuthenticationError(f"Erreur d'authentification ({api}.{method}) : {msg}")
        raise SynologyAPIError(f"Erreur API {api}.{method} : {msg}")

    # ── Dossiers ──────────────────────────────────────────────────────────────

    def list_folders(
        self,
        parent_id: Optional[int] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Liste les dossiers de l'espace partagé.
        parent_id=None → dossiers racine.
        Retourne [{"id": int, "name": str, ...}, ...]
        """
        if parent_id is None:
            data = self._api("SYNO.FotoTeam.Browse.Folder", "list_parents")
        else:
            data = self._api(
                "SYNO.FotoTeam.Browse.Folder", "list",
                id=parent_id, offset=offset, limit=limit,
            )
        return data.get("list", [])

    # ── Photos ────────────────────────────────────────────────────────────────

    def list_items(
        self,
        folder_id: Optional[int] = None,
        limit: int = 500,
        offset: int = 0,
        date_from: Optional[datetime.date] = None,
        date_to: Optional[datetime.date] = None,
    ) -> list[dict[str, Any]]:
        """
        Liste les photos de l'espace partagé.
        Utilise list_with_filter si date_from ou date_to est fourni.
        Retourne [{"id": int, "filename": str, "time": int, "folder_id": int, ...}, ...]
        Le champ "time" est un timestamp Unix (secondes depuis 1970).
        """
        params: dict[str, Any] = {
            "offset":     offset,
            "limit":      limit,
            "additional": json.dumps(["thumbnail"]),
        }
        if folder_id is not None:
            params["folder_id"] = folder_id

        if date_from or date_to:
            t_from = _to_ts(date_from) if date_from else 0
            t_to   = _to_ts_end(date_to) if date_to else 2_147_483_647
            params["time"] = json.dumps([{"start_time": t_from, "end_time": t_to}])
            data = self._api("SYNO.FotoTeam.Browse.Item", "list_with_filter", **params)
        else:
            data = self._api("SYNO.FotoTeam.Browse.Item", "list", **params)

        return data.get("list", [])

    def count_items(
        self,
        folder_id: Optional[int] = None,
        date_from: Optional[datetime.date] = None,
        date_to: Optional[datetime.date] = None,
    ) -> int:
        """
        Retourne le nombre de photos correspondant aux filtres.
        Sans filtre → total de toutes les photos de l'espace partagé.
        """
        params: dict[str, Any] = {}
        if folder_id is not None:
            params["folder_id"] = folder_id

        if date_from or date_to:
            t_from = _to_ts(date_from) if date_from else 0
            t_to   = _to_ts_end(date_to) if date_to else 2_147_483_647
            params["time"] = json.dumps([{"start_time": t_from, "end_time": t_to}])
            data = self._api("SYNO.FotoTeam.Browse.Item", "count_with_filter", **params)
        else:
            data = self._api("SYNO.FotoTeam.Browse.Item", "count", **params)

        return int(data.get("count", 0))

    # ── Albums ────────────────────────────────────────────────────────────────

    def find_album(self, name: str) -> Optional[int]:
        """
        Cherche un album par nom exact parmi les NormalAlbums.
        Retourne l'album_id ou None si introuvable.
        """
        offset = 0
        limit  = 100
        while True:
            data   = self._api("SYNO.Foto.Browse.NormalAlbum", "list", version=1,
                               offset=offset, limit=limit)
            albums = data.get("list", [])
            for a in albums:
                if a.get("name") == name:
                    return int(a["id"])
            if len(albums) < limit:
                break
            offset += limit
        return None

    def create_album(self, name: str) -> int:
        """
        Crée un album vide.
        En dry_run → logue l'action et retourne -1.
        Retourne l'album_id assigné par Synology.
        """
        if self.dry_run:
            log.info("[DRY-RUN] Créerait l'album : « %s »", name)
            return -1

        data     = self._api("SYNO.Foto.Browse.NormalAlbum", "create", version=1, name=name)
        album_id = int(data["album"]["id"])
        log.info("Album créé : « %s » (id=%d) — configurez le partage dans Synology Photos", name, album_id)
        return album_id

    def list_album_item_ids(self, album_id: int) -> list[int]:
        """Retourne la liste de tous les item_ids contenus dans l'album."""
        ids    = []
        offset = 0
        limit  = 500
        while True:
            data  = self._api("SYNO.Foto.Browse.Item", "list", version=1,
                              album_id=album_id, offset=offset, limit=limit)
            batch = data.get("list", [])
            ids.extend(int(item["id"]) for item in batch if "id" in item)
            if len(batch) < limit:
                break
            offset += limit
        return ids

    def clear_album(self, album_id: int) -> None:
        """
        Vide l'album de toutes ses photos (les photos restent intactes sur le NAS).
        En dry_run → logue seulement.
        """
        if self.dry_run:
            log.info("[DRY-RUN] Viderait l'album id=%d", album_id)
            return

        item_ids = self.list_album_item_ids(album_id)
        if not item_ids:
            log.debug("Album id=%d déjà vide", album_id)
            return

        for start in range(0, len(item_ids), _BATCH):
            batch = item_ids[start:start + _BATCH]
            self._api("SYNO.Foto.Browse.NormalAlbum", "delete_item", version=1,
                      id=album_id, item=json.dumps(batch))

        log.info("Album id=%d vidé (%d photos supprimées)", album_id, len(item_ids))

    def add_items_to_album(self, album_id: int, item_ids: list[int]) -> None:
        """
        Ajoute des photos à un album via leurs item_id — zéro copie physique.
        Procède par lots de 100 pour respecter les limites de l'API.
        En dry_run → logue seulement.
        """
        if self.dry_run:
            log.info("[DRY-RUN] Ajouterait %d photos à l'album id=%d", len(item_ids), album_id)
            return

        for start in range(0, len(item_ids), _BATCH):
            batch = item_ids[start:start + _BATCH]
            self._api(
                "SYNO.Foto.Browse.NormalAlbum", "add_item",
                version=1,
                id=album_id,
                item=json.dumps(batch),
            )
            log.debug("Lot %d–%d ajouté (album id=%d)", start, start + len(batch), album_id)

        log.info("%d photos ajoutées à l'album id=%d", len(item_ids), album_id)

    def delete_album(self, album_id: int) -> None:
        """
        Supprime l'album (les photos restent intactes sur le NAS).
        En dry_run → logue seulement. Réservé aux tests.
        """
        if self.dry_run:
            log.info("[DRY-RUN] Supprimerait l'album id=%d", album_id)
            return

        self._api("SYNO.Foto.Browse.NormalAlbum", "delete", version=1, id=album_id)
        log.info("Album id=%d supprimé", album_id)

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self) -> "SynologyPhotosClient":
        self.login()
        return self

    def __exit__(self, *_: Any) -> None:
        self.logout()


# ── Utilitaires date ──────────────────────────────────────────────────────────
def _to_ts(d: datetime.date) -> int:
    """Convertit une date en timestamp Unix (début de journée, minuit local)."""
    return int(datetime.datetime.combine(d, datetime.time.min).timestamp())


def _to_ts_end(d: datetime.date) -> int:
    """Convertit une date en timestamp Unix (fin de journée, 23:59:59 local)."""
    return int(datetime.datetime.combine(d, datetime.time.max).timestamp())
