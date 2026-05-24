"""
Historique des photos partagées — évite les répétitions sur une fenêtre glissante.

Stocké dans cache/history.json. Chaque entrée représente une exécution réussie :
  { "date": "YYYY-MM-DD", "theme": "anniversary", "photo_ids": [123, 456, ...] }
"""
from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path

log = logging.getLogger("album")

HISTORY_FILE = Path(__file__).parent / "cache" / "history.json"


class PhotoHistory:
    """
    Trace les photos publiées par thème pour éviter les répétitions.

    Usage :
        history = PhotoHistory()
        exclude = history.recent_ids("anniversary", days=30)
        # ... sélection en excluant `exclude` ...
        history.record("anniversary", today, selected_ids)
        history.save(max_days=90)
    """

    def __init__(self, path: Path = HISTORY_FILE) -> None:
        self._path = path
        self._entries: list[dict] = []
        self._load()

    # ── Lecture ───────────────────────────────────────────────────────────────

    def recent_ids(self, theme: str, days: int) -> frozenset[int]:
        """IDs des photos publiées pour ce thème dans les `days` derniers jours."""
        if days <= 0:
            return frozenset()
        cutoff = datetime.date.today() - datetime.timedelta(days=days)
        ids: set[int] = set()
        for entry in self._entries:
            if entry.get("theme") != theme:
                continue
            if self._safe_date(entry.get("date", "")) > cutoff:
                ids.update(entry.get("photo_ids", []))
        return frozenset(ids)

    # ── Écriture ──────────────────────────────────────────────────────────────

    def record(self, theme: str, date: datetime.date, photo_ids: list[int]) -> None:
        """Enregistre une exécution réussie dans l'historique en mémoire."""
        self._entries.append({
            "date":      date.isoformat(),
            "theme":     theme,
            "photo_ids": photo_ids,
        })

    def save(self, max_days: int = 90) -> None:
        """Sauvegarde sur disque en purgeant les entrées plus vieilles que max_days jours."""
        cutoff = datetime.date.today() - datetime.timedelta(days=max_days)
        kept = [e for e in self._entries if self._safe_date(e.get("date", "")) >= cutoff]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"history": kept}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.debug(
            "Historique sauvegardé : %d entrée(s) conservée(s) (fenêtre : %d jours)",
            len(kept), max_days,
        )

    # ── Interne ───────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._entries = data.get("history", [])
            log.debug("Historique chargé : %d entrée(s)", len(self._entries))
        except Exception as exc:
            log.warning("Historique illisible (%s) — réinitialisé", exc)
            self._entries = []

    @staticmethod
    def _safe_date(s: str) -> datetime.date:
        try:
            return datetime.date.fromisoformat(s)
        except (ValueError, TypeError):
            return datetime.date.min
