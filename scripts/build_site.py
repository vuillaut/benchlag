"""Builds the static site (GitHub Pages) in site/: stlite runs the Streamlit
app in the browser via Pyodide, with no Python server.

    uv run python scripts/build_site.py [--out site]
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STLITE = "1.12.3"  # bundles Streamlit 1.65

CODE = ["benchlag/__init__.py", "benchlag/app.py", "benchlag/fetch.py", "benchlag/lag.py",
        "benchlag/paths.py", "config.toml"]
DATA = ["epoch_capabilities_index/eci_scores.csv", "epoch_capabilities_index/eci_bootstraps.json",
        "epoch_capabilities_index/processed_data_for_eci.csv", "benchmark_metadata.csv", "SHA256"]
EXTRA = ["PROTOCOLE.md", "reports/latest.md", "reports/eci_lag.png", "reports/history.csv"]

PAGE = """<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Retard entre modèles d'IA</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@stlite/browser@{stlite}/build/stlite.css" />
  <style>
    #loading {{ font-family: system-ui, sans-serif; max-width: 40rem; margin: 20vh auto; padding: 0 1rem; color: #444; }}
    #loading p {{ line-height: 1.5; }}
  </style>
</head>
<body>
  <div id="root">
    <div id="loading">
      <h1>Retard entre modèles d'IA</h1>
      <p>Chargement de Python dans le navigateur (Pyodide) puis des données Epoch AI.
      Le premier chargement prend 20 à 40 secondes ; les suivants sont plus rapides grâce au cache.</p>
      <p>Données : instantané {snapshot}. <a href="PROTOCOLE.md">Protocole</a> ·
      <a href="reports/latest.md">dernier rapport (Markdown)</a></p>
    </div>
  </div>
  <script type="module">
    import {{ mount }} from "https://cdn.jsdelivr.net/npm/@stlite/browser@{stlite}/build/stlite.js";
    mount({{
      entrypoint: "benchlag/app.py",
      files: {files},
      streamlitConfig: {{ "client.toolbarMode": "viewer" }},
    }}, document.getElementById("root"));
  </script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "site")
    out = ap.parse_args().out

    raw = ROOT / "data" / "raw"
    snap = (raw / "LATEST").read_text().strip()
    if out.exists():
        shutil.rmtree(out)

    def copy(src: Path, rel: str) -> None:
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    mounted: list[str] = []
    for rel in CODE:
        copy(ROOT / rel, rel)
        mounted.append(rel)
    copy(raw / "LATEST", "data/raw/LATEST")
    mounted.append("data/raw/LATEST")
    for rel in DATA:
        path = f"data/raw/{snap}/{rel}"
        copy(raw / snap / rel, path)
        mounted.append(path)
    for rel in EXTRA:  # served for reading, not mounted in Python
        if (ROOT / rel).exists():
            copy(ROOT / rel, rel)

    files = {p: {"url": f"./{p}"} for p in mounted}
    (out / "index.html").write_text(
        PAGE.format(stlite=STLITE, snapshot=snap, files=json.dumps(files, indent=8))
    )
    (out / ".nojekyll").write_text("")
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) / 1e6
    print(f"Site built in {out} ({size:.1f} MB, snapshot {snap})")


if __name__ == "__main__":
    main()
