"""Point d'entrée : benchlag [--offline] [--target NOM] [--config config.toml]."""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from . import fetch, lag, report
from .paths import ROOT


def snapshot(cfg: dict, offline: bool) -> Path:
    raw = ROOT / "data" / "raw"
    if offline:
        return raw / (raw / "LATEST").read_text().strip()
    return fetch.fetch(cfg["source_url"], raw)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=ROOT / "config.toml")
    ap.add_argument("--offline", action="store_true", help="réutilise le dernier instantané sans télécharger")
    ap.add_argument("--target", action="append", help="remplace la liste 'target' de la config (répétable)")
    ap.add_argument("--reference", help="regex de la lignée de référence")
    ap.add_argument("--reference-org", help="restreint la référence à une organisation (ex. Anthropic)")
    ap.add_argument("--reference-label")
    ap.add_argument("--out", type=Path, default=ROOT / "reports")
    args = ap.parse_args()

    cfg = tomllib.loads(args.config.read_text())
    if args.target:
        cfg["target"] = args.target
    if args.reference or args.reference_org:
        cfg["reference_pattern"] = args.reference
        cfg["reference_label"] = args.reference_label or args.reference or args.reference_org

    snap = snapshot(cfg, args.offline)
    print(f"Instantané : {snap}")

    target = cfg["target"][0]
    eci_df = lag.load_eci(snap)
    boot = lag.load_bootstraps(snap)
    ref_models = lag.select_reference(eci_df, cfg.get("reference_pattern"), args.reference_org)

    try:
        eci = lag.eci_lag(eci_df, boot, target, ref_models)
    except ValueError as e:  # cible en avance, référence trop récente, modèle absent
        sys.exit(f"Erreur : {e}")

    # Contexte : retard sur le meilleur modèle tous labos (None si la cible est en tête).
    try:
        eci_front = lag.eci_lag(eci_df, boot, target, eci_df["Model"].tolist())
    except (lag.TargetAheadError, lag.ReferenceTooRecentError):
        eci_front = None

    scores = lag.load_scores(snap)
    table = lag.per_benchmark_lags(scores, cfg["target"], ref_models,
                                   cfg["saturation_fraction"], cfg["max_bracket_months"])
    agg = lag.aggregate(table, cfg["bootstrap_samples"], cfg["seed"], primary=target)

    md = report.write(args.out, snap, cfg, eci, eci_front, table, agg, eci_df)
    print(f"Rapport : {md}")
    print(f"ECI : retard {eci.lag_months:.1f} mois | benchmarks : médiane "
          f"{agg.get('tous', {}).get('median', float('nan')):.1f} mois (n={agg.get('tous', {}).get('n', 0)})")


if __name__ == "__main__":
    main()
