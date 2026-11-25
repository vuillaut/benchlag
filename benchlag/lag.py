"""Calcul du retard temporel d'un modèle cible sur une lignée de référence.

Principe : pour une mesure donnée (un benchmark ou l'indice ECI), on trace la
trajectoire de la lignée de référence dans le temps, on cherche la date à
laquelle elle a atteint le score du modèle cible, et on soustrait cette date
de la date de sortie du modèle cible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

DAYS_PER_MONTH = 365.25 / 12


@dataclass
class Match:
    status: str  # "interpolated" | "left_censored" | "not_reached" | "insufficient"
    date: pd.Timestamp | None = None  # date interpolée où la référence atteint la cible
    date_first_above: pd.Timestamp | None = None  # première version qui atteint la cible
    date_last_below: pd.Timestamp | None = None  # dernière version sous la cible
    ref_first: pd.Timestamp | None = None
    ref_last: pd.Timestamp | None = None


def match_date(dates: pd.Series, scores: pd.Series, target: float) -> Match:
    """Date à laquelle la frontière de la référence (max cumulé) atteint `target`.

    Entre deux versions on interpole linéairement en temps. La frontière est
    le meilleur score obtenu jusqu'ici : une version moins bonne que la
    précédente ne fait pas reculer la lignée.
    """
    # Tableaux bruts : on ne veut pas d'alignement sur les index pandas.
    df = pd.DataFrame({
        "d": pd.to_datetime(np.asarray(dates)),
        "s": np.asarray(scores, dtype=float),
    }).dropna()
    df = df.sort_values("d").reset_index(drop=True)
    if df.empty:
        return Match("insufficient")
    front = np.maximum.accumulate(df["s"].to_numpy(dtype=float))
    d = df["d"]
    m = Match("insufficient", ref_first=d.iloc[0], ref_last=d.iloc[-1])
    if target <= front[0]:
        m.status, m.date, m.date_first_above = "left_censored", d.iloc[0], d.iloc[0]
        return m
    if target > front[-1]:
        m.status, m.date_last_below = "not_reached", d.iloc[-1]
        return m
    k = int(np.argmax(front >= target))
    f0, f1 = front[k - 1], front[k]
    t0, t1 = d.iloc[k - 1], d.iloc[k]
    frac = (target - f0) / (f1 - f0)
    m.status = "interpolated"
    m.date = t0 + (t1 - t0) * frac
    m.date_first_above, m.date_last_below = t1, t0
    return m


def months(a: pd.Timestamp, b: pd.Timestamp) -> float:
    return (a - b).days / DAYS_PER_MONTH


# --------------------------------------------------------------------------
# Méthode A : indice composite ECI (Epoch Capabilities Index)
# --------------------------------------------------------------------------


@dataclass
class EciResult:
    target_name: str
    target_date: pd.Timestamp
    target_eci: float
    point: Match
    lag_months: float | None
    lag_first_above: float | None
    lag_last_below: float | None
    boot_lags: np.ndarray = field(repr=False, default_factory=lambda: np.array([]))
    boot_status: dict = field(default_factory=dict)
    reference: pd.DataFrame = field(repr=False, default_factory=pd.DataFrame)


class TargetAheadError(ValueError):
    """La cible n'est pas en retard sur la référence : le retard n'a pas de sens."""


class ReferenceTooRecentError(ValueError):
    """Toute la référence est au-dessus de la cible et sortie après elle :
    aucune version ne permet de dater le moment où la référence a atteint ce niveau."""


def _lag_from_match(m: Match, t: pd.Timestamp) -> float:
    if m.status in ("interpolated", "left_censored"):
        return months(t, m.date)
    if m.status == "not_reached":
        # La cible dépasse toute la lignée : le retard est au plus celui-ci
        # (borne haute, éventuellement négatif en réalité).
        return months(t, m.date_last_below)
    return np.nan


# --------------------------------------------------------------------------
# Chargement et choix de la référence
# --------------------------------------------------------------------------


def load_eci(snap: Path) -> pd.DataFrame:
    eci = pd.read_csv(snap / "epoch_capabilities_index" / "eci_scores.csv")
    eci["date"] = pd.to_datetime(eci["date"])
    return eci


def load_bootstraps(snap: Path) -> dict | None:
    bpath = snap / "epoch_capabilities_index" / "eci_bootstraps.json"
    if not bpath.exists():
        return None
    boot = json.loads(bpath.read_text())
    return dict(
        names=boot["model"]["names"],
        samples=np.asarray(boot["model"]["capability_samples"], dtype=float),
    )


def select_reference(
    eci: pd.DataFrame, pattern: str | None = None, organization: str | None = None
) -> list[str]:
    """Liste des modèles de la référence, par regex sur le nom et/ou par organisation."""
    mask = pd.Series(True, index=eci.index)
    if pattern:
        mask &= eci["Model"].str.contains(pattern, regex=True)
    if organization:
        mask &= eci["Organization"].astype(str).str.contains(organization, regex=False)
    return eci.loc[mask].sort_values("date")["Model"].tolist()


def eci_lag(
    eci: pd.DataFrame,
    boot: dict | None,
    target: str,
    ref_models: list[str],
    allow_ahead: bool = False,
) -> EciResult:
    """Retard de `target` sur les modèles `ref_models`, mesuré sur l'ECI.

    Lève TargetAheadError si la cible est en avance : soit aucune version de
    la référence n'atteint son niveau, soit la référence ne l'atteint
    qu'après la sortie de la cible (retard négatif).
    """
    row = eci[eci["Model"] == target]
    if row.empty:
        raise ValueError(f"{target!r} absent de l'ECI")
    ref = eci[eci["Model"].isin(ref_models) & (eci["Model"] != target)].sort_values("date")
    if ref.empty:
        raise ValueError("la référence ne contient aucun modèle")
    t_date, t_eci = row["date"].iloc[0], float(row["eci"].iloc[0])

    point = match_date(ref["date"], ref["eci"], t_eci)
    lag_point = _lag_from_match(point, t_date)
    if not allow_ahead:
        if point.status == "not_reached":
            best = ref.loc[ref["eci"].idxmax()]
            raise TargetAheadError(
                f"{target} (ECI {t_eci:.1f}) est au-dessus de toute la référence : le meilleur "
                f"modèle, {best['Model']}, plafonne à {best['eci']:.1f}. Aucun retard à mesurer."
            )
        if point.status == "left_censored" and lag_point < 0:
            first = ref.iloc[0]
            raise ReferenceTooRecentError(
                f"Tous les modèles de la référence sont au-dessus de {target} (ECI {t_eci:.1f}), et le plus "
                f"ancien, {first['Model']}, est sorti le {first['date']:%Y-%m-%d}, après {target} "
                f"({t_date:%Y-%m-%d}). Il manque des versions plus anciennes, sous le niveau de {target}, "
                f"pour dater le moment où la référence l'a atteint. Ajoutez les versions précédentes de la lignée."
            )
        if lag_point < 0:
            raise TargetAheadError(
                f"{target} (sorti le {t_date:%Y-%m-%d}) a atteint ce niveau {-lag_point:.1f} mois "
                f"avant la référence (croisement le {point.date:%Y-%m-%d}) : c'est une avance, pas un retard."
            )

    res = EciResult(
        target, t_date, t_eci, point, lag_point,
        months(t_date, point.date_first_above) if point.date_first_above is not None else None,
        months(t_date, point.date_last_below) if point.date_last_below is not None else None,
        reference=ref[["Model", "date", "eci", "eci_ci_low", "eci_ci_high"]],
    )

    # Incertitude : on rejoue l'appariement sur chaque tirage bootstrap
    # publié par Epoch (incertitude conjointe cible + référence).
    if boot is not None:
        idx = {n: i for i, n in enumerate(boot["names"])}
        ref_ok = ref[ref["Model"].isin(idx)]
        ref_cols = [idx[n] for n in ref_ok["Model"]]
        lags, status = [], {}
        if target in idx and len(ref_cols):
            for s in boot["samples"]:
                mm = match_date(ref_ok["date"], s[ref_cols], s[idx[target]])
                status[mm.status] = status.get(mm.status, 0) + 1
                lags.append(_lag_from_match(mm, t_date))
        res.boot_lags, res.boot_status = np.array(lags), status
    return res


# --------------------------------------------------------------------------
# Méthode B : benchmark par benchmark
# --------------------------------------------------------------------------


def load_scores(snap: Path) -> pd.DataFrame:
    """Table longue (modèle, benchmark, score, date) déjà harmonisée par Epoch.

    Epoch y garde un score par modèle et par benchmark (meilleure
    configuration de raisonnement), ramené sur [0, 1].
    """
    p = pd.read_csv(snap / "epoch_capabilities_index" / "processed_data_for_eci.csv")
    p["date"] = pd.to_datetime(p["date"])
    meta = pd.read_csv(snap / "benchmark_metadata.csv")[
        ["benchmark", "random_baseline", "score_ceiling"]
    ]
    return p.merge(meta, on="benchmark", how="left")


def per_benchmark_lags(
    scores: pd.DataFrame,
    targets: list[str],
    ref_models: list[str],
    saturation_fraction: float,
    max_bracket_months: float,
) -> pd.DataFrame:
    is_ref = scores["Model"].isin(set(ref_models) - set(targets))
    rows = []
    for bench, g in scores.groupby("benchmark"):
        tgt = None
        for name in targets:
            hit = g[g["Model"] == name]
            if not hit.empty:
                tgt = hit.iloc[0]
                break
        if tgt is None:
            continue
        ref = g[is_ref.loc[g.index]]
        t_score, t_date = float(tgt["performance"]), tgt["date"]
        base = float(tgt["random_baseline"]) if pd.notna(tgt["random_baseline"]) else 0.0
        ceil = float(tgt["score_ceiling"]) if pd.notna(tgt["score_ceiling"]) else 1.0
        headroom = (t_score - base) / (ceil - base) if ceil > base else np.nan

        m = match_date(ref["date"], ref["performance"], t_score)
        bracket = (
            months(m.date_first_above, m.date_last_below)
            if m.status == "interpolated"
            else np.nan
        )
        rows.append(
            dict(
                benchmark=bench,
                target_variant=tgt["Model"],
                target_score=t_score,
                n_ref=int(ref["performance"].notna().sum()),
                ref_best=float(ref["performance"].max()) if len(ref) else np.nan,
                status=m.status,
                match_date=m.date,
                lag_months=_lag_from_match(m, t_date) if len(ref) else np.nan,
                lag_low=months(t_date, m.date_first_above) if m.date_first_above is not None else np.nan,
                lag_high=months(t_date, m.date_last_below) if m.date_last_below is not None else np.nan,
                bracket_months=bracket,
                saturated=bool(headroom >= saturation_fraction),
                imprecise=bool(bracket > max_bracket_months) if not np.isnan(bracket) else False,
            )
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    # Cible sous toute la référence alors que celle-ci est plus récente : la borne
    # « au moins X mois » est négative, donc ne dit rien.
    out["ref_too_recent"] = (out["status"] == "left_censored") & (out["lag_months"] < 0)
    out["used"] = (
        (out["n_ref"] >= 2) & ~out["saturated"] & (out["status"] != "insufficient") & ~out["ref_too_recent"]
    )
    return out.sort_values("lag_months", ascending=False).reset_index(drop=True)


def aggregate(table: pd.DataFrame, n_boot: int, seed: int, primary: str | None = None) -> dict:
    """Médiane des retards et intervalle à 90 % par bootstrap sur les benchmarks.

    Les valeurs censurées (cible sous la plus vieille version de référence, ou
    au-dessus de la plus récente) entrent avec leur borne. La médiane reste
    exacte tant que ces bornes tombent du bon côté de la médiane, ce qu'on
    vérifie en publiant aussi la médiane des seuls cas interpolés.
    """
    rng = np.random.default_rng(seed)
    used = table[table["used"]]
    out = {}
    for key, sub in {
        "tous": used,
        "interpolés": used[used["status"] == "interpolated"],
        "précis": used[(used["status"] == "interpolated") & ~used["imprecise"]],
        "version finale seule": used[used["target_variant"] == primary] if primary else used.iloc[0:0],
    }.items():
        x = sub["lag_months"].to_numpy(dtype=float)
        if len(x) == 0:
            out[key] = dict(n=0)
            continue
        boots = np.median(rng.choice(x, size=(n_boot, len(x)), replace=True), axis=1)
        out[key] = dict(
            n=len(x),
            median=float(np.median(x)),
            ci90=(float(np.percentile(boots, 5)), float(np.percentile(boots, 95))),
        )
    return out
