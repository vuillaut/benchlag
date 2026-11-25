import pandas as pd
import pytest

from benchlag.lag import match_date, months

D = pd.to_datetime(["2025-01-01", "2025-07-01", "2026-01-01"])


def test_interpolation_milieu():
    m = match_date(D, pd.Series([0.2, 0.4, 0.8]), 0.3)
    assert m.status == "interpolated"
    assert abs((m.date - pd.Timestamp("2025-04-01")).days) <= 1
    assert m.date_last_below == D[0] and m.date_first_above == D[1]


def test_regression_ignoree():
    # La 2e version régresse : la frontière reste à 0.5, on croise 0.6 entre v2 et v3.
    m = match_date(D, pd.Series([0.5, 0.3, 0.7]), 0.6)
    assert m.status == "interpolated"
    assert m.date_last_below == D[1]
    assert abs((m.date - pd.Timestamp("2025-10-01")).days) <= 2


def test_censures():
    assert match_date(D, pd.Series([0.2, 0.4, 0.8]), 0.1).status == "left_censored"
    assert match_date(D, pd.Series([0.2, 0.4, 0.8]), 0.9).status == "not_reached"


def test_months():
    assert months(pd.Timestamp("2026-01-01"), pd.Timestamp("2025-01-01")) == pytest.approx(12, abs=0.05)


def test_index_non_alignes():
    # Régression : dates et scores avec des index pandas différents.
    dates = pd.Series(D, index=[10, 20, 30])
    m = match_date(dates, pd.Series([0.2, 0.4, 0.8]), 0.3)
    assert m.status == "interpolated"


# --- Erreur quand la cible est en avance --------------------------------------

from benchlag.lag import TargetAheadError, eci_lag  # noqa: E402


def _eci(rows):
    df = pd.DataFrame(rows, columns=["Model", "date", "eci"])
    df["date"] = pd.to_datetime(df["date"])
    df["eci_ci_low"], df["eci_ci_high"] = df["eci"] - 1, df["eci"] + 1
    return df


def test_avance_hors_reference():
    eci = _eci([("R1", "2025-01-01", 100), ("R2", "2025-07-01", 110), ("C", "2025-06-01", 120)])
    with pytest.raises(TargetAheadError, match="au-dessus"):
        eci_lag(eci, None, "C", ["R1", "R2"])


def test_avance_retard_negatif():
    # La référence atteint 105 vers le 1er avril, la cible l'avait dès le 1er janvier.
    eci = _eci([("R1", "2025-01-01", 100), ("R2", "2025-07-01", 110), ("C", "2025-01-01", 105)])
    eci.loc[eci.Model == "R1", "date"] = pd.Timestamp("2024-12-01")
    with pytest.raises(TargetAheadError, match="avance"):
        eci_lag(eci, None, "C", ["R1", "R2"])


def test_retard_normal_et_allow_ahead():
    eci = _eci([("R1", "2025-01-01", 100), ("R2", "2025-07-01", 110), ("C", "2026-01-01", 105)])
    assert eci_lag(eci, None, "C", ["R1", "R2"]).lag_months == pytest.approx(9.0, abs=0.2)
    eci2 = _eci([("R1", "2025-01-01", 100), ("C", "2025-06-01", 120)])
    assert eci_lag(eci2, None, "C", ["R1"], allow_ahead=True).point.status == "not_reached"


def test_reference_trop_recente():
    # Cas GPT-6 Luna vs GPT-6.2 Astra seul : la référence est au-dessus et plus récente.
    from benchlag.lag import ReferenceTooRecentError

    eci = _eci([("Astra", "2026-11-17", 172.8), ("Luna", "2026-09-22", 156.5)])
    with pytest.raises(ReferenceTooRecentError, match="plus anciennes"):
        eci_lag(eci, None, "Luna", ["Astra"])
    # Ce n'est pas une « avance » : l'erreur ne doit pas être TargetAheadError.
    with pytest.raises(ValueError) as exc:
        eci_lag(eci, None, "Luna", ["Astra"])
    assert not isinstance(exc.value, TargetAheadError)


def test_borne_basse_positive_conservee():
    # Référence au-dessus mais plus ancienne : retard d'au moins 6 mois, calcul normal.
    eci = _eci([("R1", "2025-01-01", 120), ("C", "2025-07-02", 110)])
    r = eci_lag(eci, None, "C", ["R1"])
    assert r.point.status == "left_censored" and r.lag_months == pytest.approx(6.0, abs=0.1)
