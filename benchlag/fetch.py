"""Téléchargement et instantané daté des données Epoch AI."""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import urllib.request
import zipfile
from pathlib import Path

ALLOWED_SUFFIXES = {".csv", ".json", ".md"}


def fetch(url: str, raw_dir: Path) -> Path:
    """Télécharge le zip, l'extrait dans raw_dir/<date>/ et renvoie ce dossier.

    Si le contenu n'a pas changé depuis le dernier instantané, on réutilise
    celui-ci au lieu d'en créer un nouveau.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "benchlag/0.1"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = resp.read()
    digest = hashlib.sha256(payload).hexdigest()[:16]

    raw_dir.mkdir(parents=True, exist_ok=True)
    latest = raw_dir / "LATEST"
    if latest.exists():
        prev = raw_dir / latest.read_text().strip()
        if (prev / "SHA256").exists() and (prev / "SHA256").read_text().strip() == digest:
            return prev

    snap = raw_dir / dt.date.today().isoformat()
    snap.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        for info in zf.infolist():
            name = Path(info.filename)
            # Archive non fiable : pas de chemins absolus ni de "..", et
            # uniquement des fichiers de données.
            if info.is_dir() or name.is_absolute() or ".." in name.parts:
                continue
            if name.suffix.lower() not in ALLOWED_SUFFIXES:
                continue
            dest = snap / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(info))
    (snap / "SHA256").write_text(digest + "\n")
    latest.write_text(snap.name + "\n")
    return snap
