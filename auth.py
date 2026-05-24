"""Authentification à l'API Synology et gestion de session."""
from __future__ import annotations
from typing import Optional
import requests


class SynologySession:
    """Maintient une session authentifiée avec l'API Synology Photos."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        otp_secret: Optional[str] = None,
    ) -> None:
        self.base_url = f"{host.rstrip('/')}:{port}/webapi"
        self.username = username
        self.password = password
        self.otp_secret = otp_secret
        self._sid: Optional[str] = None  # identifiant de session retourné par Synology

    def login(self) -> None:
        """Ouvre une session sur le NAS. Lève une exception si les identifiants sont incorrects."""
        # TODO

    def logout(self) -> None:
        """Ferme proprement la session."""
        # TODO

    def get(self, api: str, method: str, **params) -> dict:
        """Effectue un appel GET authentifié à l'API Synology."""
        # TODO

    def __enter__(self) -> "SynologySession":
        self.login()
        return self

    def __exit__(self, *_) -> None:
        self.logout()
