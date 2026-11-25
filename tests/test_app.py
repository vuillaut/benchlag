from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "benchlag" / "app.py")
HAS_DATA = (Path(APP).parent.parent / "data" / "raw" / "LATEST").exists()
pytestmark = pytest.mark.skipif(not HAS_DATA, reason="no local snapshot")


def test_page_par_defaut():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    assert at.metric[0].value.endswith("mois")
    assert not at.error


def test_cible_en_avance_affiche_une_erreur():
    at = AppTest.from_file(APP, default_timeout=120).run()
    sb = next(s for s in at.selectbox if s.label == "Modèle à évaluer")
    sb.set_value("Claude Fable 5.2").run()
    assert not at.exception
    assert any("Pas de retard" in e.value for e in at.error)


def test_reference_trop_recente_affiche_un_avertissement():
    at = AppTest.from_file(APP, default_timeout=120).run()
    next(s for s in at.selectbox if s.label == "Lignée").set_value("Personnalisée").run()
    next(t for t in at.text_input if t.label == "Regex sur le nom").set_value("^GPT-6.2 Astra$").run()
    next(s for s in at.selectbox if s.label == "Modèle à évaluer").set_value("GPT-6 Luna").run()
    assert not at.exception
    assert not any("Pas de retard" in e.value for e in at.error)
    assert any("Référence insuffisante" in w.value for w in at.warning)
