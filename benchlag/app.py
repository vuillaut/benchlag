"""Interface graphique : uv run benchlag-ui (ou streamlit run benchlag/app.py)."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

# Streamlit puts the script's folder (benchlag/) on the path, not the project
# root: needed to import the package, both in stlite and without installing it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import altair as alt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from benchlag import fetch, lag  # noqa: E402
from benchlag.paths import ROOT  # noqa: E402

# In the browser (stlite / Pyodide on GitHub Pages): no network download, the
# data is refreshed by the GitHub Action.
IN_BROWSER = sys.platform == "emscripten"

st.set_page_config(page_title="Retard entre modèles", layout="wide")

CFG = tomllib.loads((ROOT / "config.toml").read_text())
RAW = ROOT / "data" / "raw"
# Palette catégorielle de référence (emplacements 1 et 2) + gris neutre.
C_REF, C_TARGET, C_FRONT = "#257de0", "#f47230", "#9c9c9c"

PRESETS: dict[str, dict] = {
    "Claude Opus": dict(pattern=r"^Claude (?:\d+ )?Opus"),
    "Tous les modèles Anthropic": dict(org="Anthropic"),
    "GPT (OpenAI)": dict(pattern=r"^GPT-"),
    "Tous les modèles OpenAI": dict(org="OpenAI"),
    "Gemini (Google DeepMind)": dict(pattern=r"^Gemini"),
    "Frontière tous labos": dict(),
    "Personnalisée": dict(),
}
STATUS_FR = {
    "interpolated": "atteint",
    "left_censored": "sous la 1re version",
    "not_reached": "jamais atteint",
    "insufficient": "données insuffisantes",
}


# --------------------------------------------------------------------------
# Données
# --------------------------------------------------------------------------


def current_snapshot() -> Path:
    latest = RAW / "LATEST"
    if not latest.exists() and IN_BROWSER:
        st.error("Données absentes du site.")
        st.stop()
    if not latest.exists():
        with st.spinner("Premier téléchargement des données Epoch AI…"):
            return fetch.fetch(CFG["source_url"], RAW)
    return RAW / latest.read_text().strip()


@st.cache_data(show_spinner="Chargement des données…")
def load(snap: str):
    p = Path(snap)
    return lag.load_eci(p), lag.load_bootstraps(p), lag.load_scores(p)


snap = current_snapshot()
eci_df, boot, scores = load(str(snap))
models_by_date = eci_df.sort_values("date", ascending=False)["Model"].tolist()
eci_by_model = eci_df.set_index("Model")


def label(m: str) -> str:
    r = eci_by_model.loc[m]
    return f"{m} · {r['date']:%Y-%m-%d} · ECI {r['eci']:.1f}"


# --------------------------------------------------------------------------
# Barre latérale : référence et réglages
# --------------------------------------------------------------------------

with st.sidebar:
    st.header("Référence")
    preset = st.selectbox("Lignée", list(PRESETS), index=0)
    spec = PRESETS[preset]
    pattern, org = spec.get("pattern"), spec.get("org")
    if preset == "Personnalisée":
        pattern = st.text_input("Regex sur le nom", value=r"^Claude") or None
        orgs = ["(toutes)"] + sorted(eci_df["Organization"].dropna().unique())
        o = st.selectbox("Organisation", orgs)
        org = None if o == "(toutes)" else o
    try:
        suggested = lag.select_reference(eci_df, pattern, org)
    except Exception as e:  # regex invalide
        st.error(f"Regex invalide : {e}")
        suggested = []
    ref_models = st.multiselect(
        "Modèles retenus (modifiables)",
        options=models_by_date,
        default=suggested,
        key=f"ref::{preset}::{pattern}::{org}",
    )
    ref_label = st.text_input("Nom affiché", value=preset if preset != "Personnalisée" else (pattern or org or "Référence"))

    with st.expander("Réglages de la méthode"):
        sat = st.slider("Seuil de saturation (part de la marge utile)", 0.5, 1.0, float(CFG["saturation_fraction"]), 0.01)
        bracket = st.slider("Encadrement jugé imprécis au-delà de (mois)", 1, 24, int(CFG["max_bracket_months"]))

    st.divider()
    st.caption(f"Données [Epoch AI](https://epoch.ai/benchmarks), instantané **{snap.name}** (CC BY 4.0)")
    if IN_BROWSER:
        st.caption("Mise à jour automatique le 1er et le 15 de chaque mois.")
    elif st.button("Mettre à jour les données"):
        with st.spinner("Téléchargement…"):
            new = fetch.fetch(CFG["source_url"], RAW)
        st.cache_data.clear()
        st.toast("Déjà à jour." if new == snap else f"Nouvel instantané : {new.name}")
        st.rerun()

st.title("Retard entre modèles d'IA")
st.caption(
    "Le retard est l'écart entre la sortie d'un modèle et la date à laquelle la référence a atteint son niveau. "
    "Méthode détaillée dans `PROTOCOLE.md`."
)

if not ref_models:
    st.warning("Choisissez au moins un modèle de référence dans la barre latérale.")
    st.stop()


# --------------------------------------------------------------------------
# Graphiques
# --------------------------------------------------------------------------


def trajectory_chart(res: lag.EciResult) -> alt.LayerChart:
    ref = res.reference.sort_values("date").copy()
    ref["Série"] = ref_label
    tooltip = [
        alt.Tooltip("Model:N", title="Modèle"),
        alt.Tooltip("date:T", title="Sortie", format="%Y-%m-%d"),
        alt.Tooltip("eci:Q", title="ECI", format=".1f"),
        alt.Tooltip("eci_ci_low:Q", title="IC bas", format=".1f"),
        alt.Tooltip("eci_ci_high:Q", title="IC haut", format=".1f"),
    ]
    x = alt.X("date:T", title="Date de sortie")
    y_scale = alt.Scale(zero=False)
    color = alt.Color(
        "Série:N",
        scale=alt.Scale(domain=[ref_label, res.target_name], range=[C_REF, C_TARGET]),
        legend=alt.Legend(orient="top-left", title=None),
    )
    base = alt.Chart(ref)
    errs = base.mark_rule(strokeWidth=1.5).encode(
        x=x, y=alt.Y("eci_ci_low:Q", scale=y_scale, title="ECI"), y2="eci_ci_high:Q", color=color
    )
    line = base.mark_line(strokeWidth=2).encode(x=x, y=alt.Y("eci:Q", scale=y_scale), color=color)
    pts = base.mark_point(filled=True, size=80, stroke="white", strokeWidth=2).encode(
        x=x, y="eci:Q", color=color, tooltip=tooltip
    )
    names = base.mark_text(align="left", dx=7, dy=10, fontSize=11).encode(x=x, y="eci:Q", text="Model:N")

    tgt = pd.DataFrame([{
        "Model": res.target_name, "date": res.target_date, "eci": res.target_eci,
        "eci_ci_low": eci_by_model.loc[res.target_name, "eci_ci_low"],
        "eci_ci_high": eci_by_model.loc[res.target_name, "eci_ci_high"], "Série": res.target_name,
    }])
    t_err = alt.Chart(tgt).mark_rule(strokeWidth=1.5).encode(x=x, y="eci_ci_low:Q", y2="eci_ci_high:Q", color=color)
    t_pt = alt.Chart(tgt).mark_point(filled=True, size=110, stroke="white", strokeWidth=2).encode(
        x=x, y="eci:Q", color=color, tooltip=tooltip
    )
    layers = [errs, line, pts, names, t_err, t_pt]

    if res.point.date is not None:
        seg = pd.DataFrame([{
            "d0": res.point.date, "d1": res.target_date, "eci": res.target_eci,
            "txt": f"{res.lag_months:.1f} mois",
            "mid": res.point.date + (res.target_date - res.point.date) / 2,
        }])
        layers += [
            alt.Chart(seg).mark_rule(strokeDash=[5, 4], strokeWidth=1.5, color=C_TARGET).encode(
                x="d0:T", x2="d1:T", y="eci:Q"
            ),
            # Sous la ligne pointillée : au-dessus, le texte croise les étiquettes de la référence.
            alt.Chart(seg).mark_text(dy=16, fontSize=13, fontWeight="bold").encode(x="mid:T", y="eci:Q", text="txt:N"),
        ]
    return alt.layer(*layers).properties(height=430)


def compare_chart(df: pd.DataFrame) -> alt.LayerChart:
    order = df.sort_values("Retard ECI (mois)", ascending=False)["Modèle"].tolist()
    y = alt.Y("Modèle:N", sort=order, title=None, axis=alt.Axis(labelLimit=260, labelFontSize=12))
    tooltip = [
        alt.Tooltip("Modèle:N"),
        alt.Tooltip("Sortie:T", format="%Y-%m-%d"),
        alt.Tooltip("Retard ECI (mois):Q", format=".1f"),
        alt.Tooltip("IC bas:Q", format=".1f"),
        alt.Tooltip("IC haut:Q", format=".1f"),
        alt.Tooltip("Médiane benchmarks (mois):Q", format=".1f"),
    ]
    base = alt.Chart(df)
    rule = base.mark_rule(strokeWidth=2, color=C_REF, opacity=0.6).encode(
        y=y, x=alt.X("IC bas:Q", title=f"Retard sur {ref_label} (mois, IC 90 %)"), x2="IC haut:Q", tooltip=tooltip
    )
    dot = base.mark_point(filled=True, size=110, color=C_REF, stroke="white", strokeWidth=2).encode(
        y=y, x="Retard ECI (mois):Q", tooltip=tooltip
    )
    txt = base.mark_text(align="left", dx=10, dy=-10, fontSize=11).encode(
        y=y, x="Retard ECI (mois):Q", text=alt.Text("Retard ECI (mois):Q", format=".1f")
    )
    return alt.layer(rule, dot, txt).properties(height=max(180, 52 * len(df)))


# --------------------------------------------------------------------------
# Onglets
# --------------------------------------------------------------------------

tab1, tab2 = st.tabs(["Un modèle", "Comparer plusieurs modèles"])

with tab1:
    c1, c2 = st.columns([2, 3])
    default_target = CFG["target"][0] if CFG["target"][0] in models_by_date else models_by_date[0]
    target = c1.selectbox("Modèle à évaluer", models_by_date, index=models_by_date.index(default_target), format_func=label)
    fallback_default = [m for m in models_by_date if m != target and m.startswith(target)]
    fallbacks = c2.multiselect(
        "Variantes de repli (benchmarks où le modèle principal n'a pas de score)",
        [m for m in models_by_date if m != target],
        default=fallback_default,
        key=f"fb::{target}",
    )

    try:
        res = lag.eci_lag(eci_df, boot, target, ref_models)
    except lag.TargetAheadError as e:
        st.error(f"**Pas de retard à mesurer.** {e}")
        res = None
    except lag.ReferenceTooRecentError as e:
        st.warning(f"**Référence insuffisante.** {e}")
        res = None
    except ValueError as e:
        st.error(str(e))
        res = None

    if res is not None:
        try:
            front = lag.eci_lag(eci_df, boot, target, eci_df["Model"].tolist())
        except (lag.TargetAheadError, lag.ReferenceTooRecentError):
            front = None
        table = lag.per_benchmark_lags(scores, [target, *fallbacks], ref_models, sat, bracket)
        agg = lag.aggregate(table, CFG["bootstrap_samples"], CFG["seed"], primary=target) if not table.empty else {}
        b = res.boot_lags
        ci = (np.nanpercentile(b, 5), np.nanpercentile(b, 95)) if len(b) else (np.nan, np.nan)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Retard (indice ECI)", f"{res.lag_months:.1f} mois",
                  help="Écart entre la sortie du modèle et la date où la référence atteint son ECI.")
        m2.metric("Intervalle à 90 %", f"{ci[0]:.1f} – {ci[1]:.1f} mois", help=f"{len(b)} tirages bootstrap d'Epoch")
        a = agg.get("tous", {})
        m3.metric("Médiane des benchmarks", f"{a['median']:.1f} mois" if a.get("n") else "–",
                  help=f"{a.get('n', 0)} benchmarks retenus" + (
                      f", IC 90 % {a['ci90'][0]:.1f} – {a['ci90'][1]:.1f}" if a.get("n") else ""))
        m4.metric("Retard sur la frontière tous labos", f"{front.lag_months:.1f} mois" if front else "en tête")

        bounds = ""
        if res.lag_first_above is not None and res.lag_last_below is not None:
            bounds = (f" En versions réelles : {res.lag_first_above:.1f} mois sur la première version au-dessus, "
                      f"{res.lag_last_below:.1f} mois sur la dernière en dessous.")
        elif res.point.status == "left_censored":
            bounds = " La cible est sous la plus ancienne version de la référence : le retard est **au moins** cette valeur."
        st.markdown(
            f"**{target}** (sorti le {res.target_date:%Y-%m-%d}, ECI {res.target_eci:.1f}) : la lignée "
            f"{ref_label} a atteint ce niveau vers le **{res.point.date:%Y-%m-%d}**.{bounds}"
        )

        st.altair_chart(trajectory_chart(res), width="stretch")

        st.subheader("Détail par benchmark")
        if table.empty:
            st.info("Aucun benchmark commun entre ce modèle et la référence.")
        else:
            show = table.assign(
                status=table["status"].map(STATUS_FR),
                match_date=pd.to_datetime(table["match_date"]).dt.date,
            )[["benchmark", "target_variant", "target_score", "ref_best", "n_ref", "status", "match_date",
               "lag_months", "lag_low", "lag_high", "saturated", "imprecise", "used"]]
            st.dataframe(
                show,
                hide_index=True,
                width="stretch",
                column_config={
                    "benchmark": "Benchmark",
                    "target_variant": "Variante",
                    "target_score": st.column_config.NumberColumn("Score", format="%.3f"),
                    "ref_best": st.column_config.NumberColumn("Meilleur réf.", format="%.3f"),
                    "n_ref": "Versions réf.",
                    "status": "Statut",
                    "match_date": "Croisement",
                    "lag_months": st.column_config.NumberColumn("Retard (mois)", format="%.1f"),
                    "lag_low": st.column_config.NumberColumn("Borne basse", format="%.1f"),
                    "lag_high": st.column_config.NumberColumn("Borne haute", format="%.1f"),
                    "saturated": "Saturé",
                    "imprecise": "Imprécis",
                    "used": "Retenu",
                },
            )
            st.download_button("Télécharger le tableau (CSV)", table.to_csv(index=False),
                               file_name=f"retard_{target}_{ref_label}.csv".replace(" ", "_"), mime="text/csv")

with tab2:
    defaults = [m for m in ["Mistral Large 4", "Kimi K3.1 Pro", "DeepSeek V4.1 Flash 1017", "Qwen3.8 Max (0902)",
                            "Grok 4.7", "GLM-5.3"] if m in models_by_date]
    targets = st.multiselect("Modèles à comparer", models_by_date, default=defaults, format_func=label)
    rows, ahead, missing = [], [], []
    for t in targets:
        try:
            r = lag.eci_lag(eci_df, boot, t, ref_models)
        except lag.TargetAheadError as e:
            ahead.append((t, str(e)))
            continue
        except ValueError as e:
            missing.append((t, str(e)))
            continue
        tb = lag.per_benchmark_lags(scores, [t], ref_models, sat, bracket)
        ag = lag.aggregate(tb, CFG["bootstrap_samples"], CFG["seed"]) if not tb.empty else {}
        bl = r.boot_lags
        rows.append({
            "Modèle": t,
            "Organisation": eci_by_model.loc[t, "Organization"],
            "Sortie": r.target_date,
            "ECI": r.target_eci,
            "Retard ECI (mois)": r.lag_months,
            "IC bas": np.nanpercentile(bl, 5) if len(bl) else np.nan,
            "IC haut": np.nanpercentile(bl, 95) if len(bl) else np.nan,
            "Médiane benchmarks (mois)": ag.get("tous", {}).get("median", np.nan),
            "Benchmarks": ag.get("tous", {}).get("n", 0),
        })
    if rows:
        df = pd.DataFrame(rows)
        st.altair_chart(compare_chart(df), width="stretch")
        st.dataframe(
            df.sort_values("Retard ECI (mois)"),
            hide_index=True,
            width="stretch",
            column_config={
                "Sortie": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "ECI": st.column_config.NumberColumn(format="%.1f"),
                "Retard ECI (mois)": st.column_config.NumberColumn(format="%.1f"),
                "IC bas": st.column_config.NumberColumn(format="%.1f"),
                "IC haut": st.column_config.NumberColumn(format="%.1f"),
                "Médiane benchmarks (mois)": st.column_config.NumberColumn(format="%.1f"),
            },
        )
    elif targets:
        st.info("Aucun des modèles choisis n'est en retard sur la référence.")
    for t, msg in ahead:
        st.warning(f"**{t}** exclu : {msg}")
    for t, msg in missing:
        st.warning(f"**{t}** exclu : {msg}")
