"""Rapport Markdown, graphique et historique."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .lag import EciResult  # noqa: E402

STATUS_FR = {
    "interpolated": "atteint",
    "left_censored": "sous la 1re version",
    "not_reached": "jamais atteint",
    "insufficient": "données insuffisantes",
}


def _fmt(x, nd=1):
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def _d(x):
    return "–" if x is None or pd.isna(x) else pd.Timestamp(x).strftime("%Y-%m-%d")


def chart(eci: EciResult, frontier_eci: pd.DataFrame | None, ref_label: str, out: Path) -> None:
    fig = make_figure(eci, frontier_eci, ref_label)
    fig.savefig(out)
    plt.close(fig)


def make_figure(eci: EciResult, frontier_eci: pd.DataFrame | None, ref_label: str):
    ref = eci.reference.sort_values("date")
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    if frontier_eci is not None and not frontier_eci.empty:
        f = frontier_eci.sort_values("date")
        f = f[f["date"] >= ref["date"].min() - pd.Timedelta(days=90)]
        ax.step(f["date"], np.maximum.accumulate(f["eci"]), where="post", color="#bbbbbb",
                lw=1.2, label="Frontière tous labos (max cumulé)")
    ax.errorbar(ref["date"], ref["eci"], yerr=[ref["eci"] - ref["eci_ci_low"], ref["eci_ci_high"] - ref["eci"]],
                fmt="o-", color="#c96442", ms=5, lw=1.5, capsize=2, label=ref_label)
    for i, (_, r) in enumerate(ref.iterrows()):
        # Étiquettes alternées dessous-droite / dessus-gauche pour éviter les chevauchements.
        below = i % 2 == 0
        ax.annotate(r["Model"].replace("Claude Opus ", "Opus ").replace("Claude 3 Opus", "Opus 3"),
                    (r["date"], r["eci"]), xytext=(5, -12) if below else (-5, 8),
                    ha="left" if below else "right", textcoords="offset points", fontsize=7, color="#7a3b26")
    ax.scatter([eci.target_date], [eci.target_eci], color="#2f5fb3", zorder=5, s=40, label=eci.target_name)
    if eci.point.date is not None:
        ax.hlines(eci.target_eci, eci.point.date, eci.target_date, colors="#2f5fb3", linestyles="--", lw=1)
        ax.annotate(f"{eci.lag_months:.1f} mois", ((eci.point.date + (eci.target_date - eci.point.date) / 2),
                    eci.target_eci), xytext=(0, -13), textcoords="offset points", ha="center",
                    fontsize=9, color="#2f5fb3")
    ax.set_ylabel("Epoch Capabilities Index (ECI)")
    ax.set_xlabel("Date de sortie")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, loc="upper left")
    ax.set_title(f"Retard de {eci.target_name} sur la lignée {ref_label}", fontsize=10)
    fig.tight_layout()
    return fig


def write(
    out_dir: Path,
    snap: Path,
    cfg: dict,
    eci: EciResult,
    eci_frontier: EciResult | None,
    table: pd.DataFrame,
    agg: dict,
    eci_all: pd.DataFrame,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ref_label = cfg["reference_label"]
    target = cfg["target"][0]
    chart(eci, eci_all, ref_label, out_dir / "eci_lag.png")

    b = eci.boot_lags
    ci = (np.percentile(b, 5), np.percentile(b, 95)) if len(b) else (np.nan, np.nan)
    a_all = agg.get("tous", {})
    a_pre = agg.get("précis", {})

    L = []
    L.append(f"# Retard de {target} sur {ref_label}\n")
    L.append(f"Calculé le {dt.date.today().isoformat()} à partir de l'instantané Epoch AI `{snap.name}` "
             f"(données sous licence CC BY 4.0, [epoch.ai/benchmarks](https://epoch.ai/benchmarks)).\n")
    L.append("## Résultat\n")
    L.append(f"- **Indice composite ECI** : {target} ({_d(eci.target_date)}) obtient "
             f"{eci.target_eci:.1f}. La lignée {ref_label} a atteint ce niveau vers le "
             f"**{_d(eci.point.date)}**, soit un retard de **{_fmt(eci.lag_months)} mois** "
             f"(IC 90 % : {_fmt(ci[0])} à {_fmt(ci[1])} mois, {len(b)} tirages bootstrap).")
    if eci.lag_first_above is not None and eci.lag_last_below is not None:
        L.append(f"  - En versions réelles : entre {_fmt(eci.lag_first_above)} mois "
                 f"(première version d'Opus au-dessus) et {_fmt(eci.lag_last_below)} mois "
                 f"(dernière version en dessous).")
    if a_all.get("n"):
        L.append(f"- **Benchmark par benchmark** : médiane {_fmt(a_all['median'])} mois "
                 f"(IC 90 % : {_fmt(a_all['ci90'][0])} à {_fmt(a_all['ci90'][1])}) sur {a_all['n']} benchmarks.")
    if a_pre.get("n"):
        L.append(f"  - Sur les seuls benchmarks bien encadrés ({a_pre['n']}) : médiane "
                 f"{_fmt(a_pre['median'])} mois (IC 90 % : {_fmt(a_pre['ci90'][0])} à {_fmt(a_pre['ci90'][1])}).")
    a_fin = agg.get("version finale seule", {})
    if a_fin.get("n"):
        L.append(f"  - Sans repli sur la preview ({a_fin['n']} benchmarks) : médiane "
                 f"{_fmt(a_fin['median'])} mois (IC 90 % : {_fmt(a_fin['ci90'][0])} à {_fmt(a_fin['ci90'][1])}).")
    if eci_frontier is None:
        L.append("- Pour situer : à sa sortie, la cible était en tête de la frontière tous laboratoires.")
    else:
        L.append(f"- Pour situer : retard sur la frontière tous laboratoires (meilleur ECI publié à chaque date) : "
                 f"{_fmt(eci_frontier.lag_months)} mois.")
    L.append("\n![ECI](eci_lag.png)\n")

    L.append("## Détail par benchmark\n")
    L.append("Score cible = meilleure configuration publiée. *Retard* = date de sortie de la cible moins la date "
             "interpolée où la frontière Opus atteint ce score. *Bornes* = retard calculé sur la première version "
             "d'Opus au-dessus / la dernière en dessous.\n")
    L.append("| Benchmark | Variante cible | Score | Meilleur Opus | Statut | Retard (mois) | Bornes | Retenu |")
    L.append("|---|---|---:|---:|---|---:|---|---|")
    for _, r in table.iterrows():
        flags = []
        if r["saturated"]:
            flags.append("saturé")
        if r["imprecise"]:
            flags.append(f"encadrement {r['bracket_months']:.0f} mois")
        if r["n_ref"] < 2:
            flags.append("<2 Opus")
        used = "oui" if r["used"] else "non"
        if flags:
            used += f" ({', '.join(flags)})"
        sign = "≥ " if r["status"] == "left_censored" else ("≤ " if r["status"] == "not_reached" else "")
        L.append(f"| {r['benchmark']} | {r['target_variant']} | {r['target_score']:.3f} | {_fmt(r['ref_best'], 3)} "
                 f"| {STATUS_FR[r['status']]} | {sign}{_fmt(r['lag_months'])} "
                 f"| {_fmt(r['lag_low'])} – {_fmt(r['lag_high'])} | {used} |")

    L.append("\n## Trajectoire ECI de la référence\n")
    L.append("| Modèle | Sortie | ECI | IC 90 % |")
    L.append("|---|---|---:|---|")
    for _, r in eci.reference.sort_values("date").iterrows():
        L.append(f"| {r['Model']} | {_d(r['date'])} | {r['eci']:.1f} | {r['eci_ci_low']:.1f} – {r['eci_ci_high']:.1f} |")

    L.append("\nMéthode complète : voir `PROTOCOLE.md`.\n")
    md = out_dir / "latest.md"
    md.write_text("\n".join(L))

    summary = dict(
        computed_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        snapshot=snap.name,
        target=target,
        reference=ref_label,
        eci=dict(target_eci=eci.target_eci, match_date=_d(eci.point.date), lag_months=eci.lag_months,
                 ci90=list(ci), lag_bounds=[eci.lag_first_above, eci.lag_last_below],
                 bootstrap_status=eci.boot_status),
        per_benchmark=agg,
        lag_vs_frontier_months=eci_frontier.lag_months if eci_frontier else None,
    )
    (out_dir / "latest.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    table.to_csv(out_dir / "per_benchmark.csv", index=False)

    hist = out_dir / "history.csv"
    row = pd.DataFrame([dict(
        computed_at=summary["computed_at"], snapshot=snap.name, target=target,
        eci_lag=eci.lag_months, eci_ci_low=ci[0], eci_ci_high=ci[1],
        bench_median=a_all.get("median"), bench_n=a_all.get("n"),
    )])
    row.to_csv(hist, mode="a", header=not hist.exists(), index=False)
    return md
