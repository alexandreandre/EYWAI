from datetime import date

import pytest

from app.modules.dsn_export.domain.fctu import (
    ajouter_jours_ouvres,
    bloc_preavis,
    fctu_depuis_mensuelle,
    fins_a_signaler,
)
from app.modules.dsn_export.domain.signalements import SignalementEnvoye

LIGNES = [
    "S10.G00.00.001,'Martine Paie'", "S10.G00.00.005,'01'",
    "S20.G00.05.001,'01'", "S20.G00.05.005,'01122026'",
    "S21.G00.06.001,'802485169'",
    "S21.G00.11.001,'00011'",
    "S21.G00.20.001,'URSSAF'", "S21.G00.20.005,'100.00'",
    "S21.G00.30.001,'1900101234567'",
    "S21.G00.40.001,'01092026'", "S21.G00.40.007,'02'",
    "S21.G00.50.001,'31122026'", "S21.G00.50.002,'1500.00'",
    "S21.G00.62.001,'18122026'", "S21.G00.62.002,'031'",
    "S90.G00.90.001,'17'", "S90.G00.90.002,'1'",
]


SANS_PREAVIS = {"S21.G00.63.001": "90"}


def _mensuelle(lignes=LIGNES):
    return "\r\n".join(lignes) + "\r\n"


def _rubriques(texte):
    return dict(l.split(",", 1) for l in texte.strip().split("\r\n"))


def test_la_dsn_du_mois_de_sortie_devient_la_fin_de_contrat():
    texte = fctu_depuis_mensuelle(_mensuelle(), mois_solde=date(2026, 12, 18), preavis=SANS_PREAVIS)
    r = _rubriques(texte)
    assert r["S20.G00.05.001"] == "'07'"
    assert "S20.G00.05.005" not in r and "S21.G00.20.001" not in r and "S21.G00.50.002" not in r
    assert r["S21.G00.50.020"] == "'01'"
    assert r["S21.G00.62.020"] == "'01122026'"
    assert r["S90.G00.90.001"] == f"'{len(texte.strip().split(chr(13) + chr(10)))}'"
    assert texte.index("S21.G00.50.020") < texte.index("S21.G00.62.001")


def test_sans_fin_de_contrat_dans_le_mois_rien_ne_part():
    with pytest.raises(ValueError, match="fin de contrat"):
        fctu_depuis_mensuelle(_mensuelle([l for l in LIGNES if not l.startswith("S21.G00.62")]),
                              mois_solde=date(2026, 12, 18), preavis=SANS_PREAVIS)


def test_une_fin_de_contrat_ne_porte_qu_un_salarie():
    deux = LIGNES[:-2] + ["S21.G00.30.001,'2900101234567'"] + LIGNES[-2:]
    with pytest.raises(ValueError, match="un seul salarié"):
        fctu_depuis_mensuelle(_mensuelle(deux), mois_solde=date(2026, 12, 18), preavis=SANS_PREAVIS)


def test_cinq_jours_ouvres():
    # Vendredi 18/12 : lundi 21 au vendredi 25.
    assert ajouter_jours_ouvres(date(2026, 12, 18), 5) == date(2026, 12, 25)


def _cdd(eid, fin):
    return {"id": eid, "contract_type": "CDD", "contract_end_date": fin}


def test_les_fins_de_contrat_du_mois_et_a_venir():
    fins = fins_a_signaler(
        sorties=[{"employee_id": "e1", "last_working_day": "2026-11-06", "status": "validee"}],
        contrats=[_cdd("e2", "2026-12-18"), _cdd("e3", "2027-03-31"), _cdd("e4", "2026-09-15")],
        envoyes=[],
        bulletins={("e1", 2026, 11)},
        depuis=date(2026, 10, 1),
        aujourd_hui=date(2026, 11, 20),
    )
    assert [(f.employee_id, f.fin, f.a_deposer_avant, f.bulletin_pret) for f in fins] == [
        ("e1", date(2026, 11, 6), date(2026, 11, 13), True),
        ("e2", date(2026, 12, 18), date(2026, 12, 25), False),
    ]


def test_une_sortie_annulee_ou_deja_signalee_ne_revient_pas():
    envoye = SignalementEnvoye("e1", "07", "", date(2026, 11, 6), date(2026, 11, 6), False, date(2026, 11, 9))
    assert fins_a_signaler(
        sorties=[{"employee_id": "e1", "last_working_day": "2026-11-06", "status": "validee"},
                 {"employee_id": "e2", "last_working_day": "2026-11-10", "status": "annulee"}],
        contrats=[], envoyes=[envoye], bulletins=set(),
        depuis=date(2026, 10, 1), aujourd_hui=date(2026, 11, 20),
    ) == []


def test_la_sortie_saisie_prime_sur_le_terme_du_cdd():
    (f,) = fins_a_signaler(
        sorties=[{"employee_id": "e2", "last_working_day": "2026-11-27", "status": "validee"}],
        contrats=[_cdd("e2", "2026-12-18")], envoyes=[], bulletins=set(),
        depuis=date(2026, 10, 1), aujourd_hui=date(2026, 11, 20),
    )
    assert f.fin == date(2026, 11, 27)


def test_le_preavis_et_la_transaction_suivent_la_fin_de_contrat():
    # DSN-VAL, fin de CDD du 15/09 : « Sous-groupe S21.G00.63 absent après
    # S21.G00.62 », « Absence de la rubrique S21.G00.62.008 ».
    texte = fctu_depuis_mensuelle(_mensuelle(), mois_solde=date(2026, 12, 18), preavis=SANS_PREAVIS)
    lignes = texte.strip().split("\r\n")
    assert "S21.G00.62.008,'02'" in lignes
    assert lignes.index("S21.G00.63.001,'90'") == lignes.index("S21.G00.62.020,'01122026'") + 1


def test_la_base_prevoyance_sante_sort_avec_ses_cotisations():
    # DSN-VAL : « base assujettie de code 31 […] dans un signalement FCTU. Ceci n'est pas admis. »
    lignes = LIGNES[:13] + [
        "S21.G00.78.001,'03'", "S21.G00.78.004,'1500.00'", "S21.G00.81.001,'018'", "S21.G00.81.004,'-300.00'",
        "S21.G00.78.001,'31'", "S21.G00.78.004,'1500.00'", "S21.G00.79.001,'18'", "S21.G00.81.001,'059'",
        "S21.G00.81.004,'12.00'",
        "S21.G00.78.001,'02'", "S21.G00.78.004,'1500.00'",
    ] + LIGNES[13:]
    texte = fctu_depuis_mensuelle(_mensuelle(lignes), mois_solde=date(2026, 12, 18), preavis=SANS_PREAVIS)
    assert "S21.G00.78.001,'31'" not in texte and "S21.G00.81.001,'059'" not in texte
    assert "S21.G00.81.001,'018'" in texte and "S21.G00.78.001,'02'" in texte


@pytest.mark.parametrize("sortie, attendu", [
    ({"exit_type": "fin_cdd"}, {"S21.G00.63.001": "90"}),
    ({"exit_type": "rupture_conventionnelle"}, {"S21.G00.63.001": "90"}),
    ({"exit_type": "demission", "notice_indemnity_type": "executed",
      "notice_start_date": "2026-11-02", "notice_end_date": "2026-11-30"},
     {"S21.G00.63.001": "01", "S21.G00.63.002": "02112026", "S21.G00.63.003": "30112026"}),
    ({"exit_type": "licenciement", "notice_indemnity_type": "paid",
      "notice_start_date": "2026-11-02", "notice_end_date": "2026-12-31"},
     {"S21.G00.63.001": "02", "S21.G00.63.002": "02112026", "S21.G00.63.003": "31122026"}),
    ({"exit_type": "demission", "notice_indemnity_type": "waived"}, {"S21.G00.63.001": "03"}),
])
def test_le_preavis_se_lit_dans_le_dossier_de_depart(sortie, attendu):
    assert bloc_preavis(sortie) == attendu


def test_un_preavis_inconnu_ne_s_invente_pas():
    with pytest.raises(ValueError, match="Préavis"):
        bloc_preavis({"exit_type": "demission"})
