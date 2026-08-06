"""Un taux PAS saisi à la main perd la date du fichier précédent.

La période sert à juger la fraîcheur d'un taux dans le suivi RH. Un taux corrigé
au clavier n'a pas de période d'origine : le laisser hériter de celle du dernier
dépôt le ferait passer pour à jour alors que personne ne sait d'où il sort.
"""

from app.modules.employees.application.commands import _demarquer_pas_saisi_a_la_main


def _fusionne(taux=12.5, **extra):
    return {
        "mutuelle": {"adhesion": True},
        "prelevement_a_la_source": {
            "taux": taux,
            "type_taux": "01",
            "periode": "2026-05",
            **extra,
        },
    }


def test_saisie_manuelle_efface_la_periode():
    merged = _demarquer_pas_saisi_a_la_main(
        _fusionne(),
        {"prelevement_a_la_source": {"is_personnalise": True, "taux": 12.5}},
    )
    assert "periode" not in merged["prelevement_a_la_source"]
    assert merged["prelevement_a_la_source"]["taux"] == 12.5
    # Le reste du bloc et les autres spécificités sont intacts.
    assert merged["prelevement_a_la_source"]["type_taux"] == "01"
    assert merged["mutuelle"] == {"adhesion": True}


def test_ecriture_datee_conserve_sa_periode():
    """Le dépôt d'un fichier fournit la période : elle doit survivre."""
    merged = _demarquer_pas_saisi_a_la_main(
        _fusionne(),
        {"prelevement_a_la_source": {"taux": 26.8, "periode": "2026-06"}},
    )
    assert merged["prelevement_a_la_source"]["periode"] == "2026-05"


def test_modification_sans_taux_ne_touche_pas_la_periode():
    """Cocher une case sans changer le taux ne dédate rien."""
    merged = _demarquer_pas_saisi_a_la_main(
        _fusionne(),
        {"prelevement_a_la_source": {"is_personnalise": True}},
    )
    assert merged["prelevement_a_la_source"]["periode"] == "2026-05"


def test_autre_specificite_ne_touche_pas_le_pas():
    merged = _demarquer_pas_saisi_a_la_main(
        _fusionne(), {"mutuelle": {"adhesion": False}}
    )
    assert merged["prelevement_a_la_source"]["periode"] == "2026-05"


def test_bloc_sans_periode_reste_inchange():
    merged = _demarquer_pas_saisi_a_la_main(
        {"prelevement_a_la_source": {"taux": 3.0}},
        {"prelevement_a_la_source": {"taux": 3.0}},
    )
    assert merged == {"prelevement_a_la_source": {"taux": 3.0}}
