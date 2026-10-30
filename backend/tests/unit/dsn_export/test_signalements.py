from datetime import date

from app.modules.dsn_export.domain.evenements import dernier_jour_travaille
from app.modules.dsn_export.domain.signalements import (
    SignalementEnvoye,
    ajouter_jours_ouvrables,
    echeance_mensuelle,
    signalements_a_faire,
)


def _arret(du, au, saisi, *, type_="arret_maladie", subrogation=False):
    jours = [date.fromordinal(o).isoformat() for o in range(du.toordinal(), au.toordinal() + 1)]
    return {"type": type_, "selected_days": jours, "subrogation_active": subrogation,
            "arret_type": None, "created_at": f"{saisi.isoformat()}T09:00:00+00:00"}


def _envoye(nature, debut, fin, *, essai=False, le=date(2026, 10, 6)):
    return SignalementEnvoye("e1", nature, "01", debut, fin, essai, le)


def test_un_arret_sans_subrogation_se_signale_sous_cinq_jours():
    (s,) = signalements_a_faire({"e1": [_arret(date(2026, 10, 5), date(2026, 10, 9), date(2026, 10, 6))]},
                                [], depuis=date(2026, 10, 1), effectif=20)
    assert (s.nature, s.debut, s.fin_prevue, s.connu_le) == ("04", date(2026, 10, 5), date(2026, 10, 9), date(2026, 10, 6))
    assert s.a_deposer_avant == date(2026, 10, 11)


def test_saisi_avant_l_arret_le_delai_part_du_premier_jour():
    (s,) = signalements_a_faire({"e1": [_arret(date(2026, 11, 2), date(2026, 11, 20), date(2026, 10, 20))]},
                                [], depuis=None, effectif=20)
    assert s.connu_le == date(2026, 11, 2)


def test_en_subrogation_le_signalement_suit_la_dsn_mensuelle():
    (s,) = signalements_a_faire({"e1": [_arret(date(2026, 10, 5), date(2026, 10, 9), date(2026, 10, 6), subrogation=True)]},
                                [], depuis=None, effectif=20)
    assert s.a_deposer_avant == date(2026, 11, 15)
    assert echeance_mensuelle(date(2026, 12, 3), 60) == date(2027, 1, 5)


def test_une_prolongation_ne_se_signale_pas():
    arrets = [_arret(date(2026, 10, 5), date(2026, 10, 9), date(2026, 10, 6)),
              _arret(date(2026, 10, 10), date(2026, 10, 20), date(2026, 10, 9))]
    assert len(signalements_a_faire({"e1": arrets}, [], depuis=None, effectif=20)) == 1


def test_un_arret_signale_ne_revient_pas_mais_un_essai_ne_compte_pas():
    arrets = {"e1": [_arret(date(2026, 10, 5), date(2026, 10, 9), date(2026, 10, 6))]}
    assert signalements_a_faire(arrets, [_envoye("04", date(2026, 10, 5), date(2026, 10, 9))], depuis=None, effectif=20) == []
    assert len(signalements_a_faire(arrets, [_envoye("04", date(2026, 10, 5), date(2026, 10, 9), essai=True)], depuis=None, effectif=20)) == 1


def test_une_reprise_avant_la_fin_declaree_demande_un_signalement_de_reprise():
    arrets = {"e1": [_arret(date(2026, 10, 5), date(2026, 10, 9), date(2026, 10, 6))]}
    (s,) = signalements_a_faire(arrets, [_envoye("04", date(2026, 10, 5), date(2026, 10, 16))], depuis=None, effectif=20)
    assert (s.nature, s.date_reprise, s.fin_prevue) == ("05", date(2026, 10, 10), date(2026, 10, 16))
    # Reprise le samedi 10/10 : dimanche 11 sauté, cinq jours ouvrables jusqu'au vendredi 16.
    assert s.a_deposer_avant == date(2026, 10, 16)
    assert signalements_a_faire(arrets, [_envoye("04", date(2026, 10, 5), date(2026, 10, 16)),
                                         _envoye("05", date(2026, 10, 5), date(2026, 10, 16))],
                                depuis=None, effectif=20) == []


def test_un_arret_d_avant_le_point_de_depart_appartient_a_l_ancien_logiciel():
    arrets = {"e1": [_arret(date(2026, 9, 1), date(2026, 10, 4), date(2026, 10, 1))]}
    assert signalements_a_faire(arrets, [], depuis=date(2026, 10, 1), effectif=20) == []


def test_le_jour_de_l_accident_est_travaille():
    assert dernier_jour_travaille("06", date(2026, 10, 5), None) == date(2026, 10, 5)
    assert dernier_jour_travaille("01", date(2026, 10, 5), None) == date(2026, 10, 4)
    assert dernier_jour_travaille("01", date(2026, 10, 5), date(2026, 10, 5)) == date(2026, 10, 5)


def test_jours_ouvrables():
    assert ajouter_jours_ouvrables(date(2026, 10, 10), 5) == date(2026, 10, 16)


def test_un_arret_qui_reprend_un_jour_apres_le_precedent_est_a_verifier():
    # Comitech, octobre 2026 : arrêt continu depuis mai, sauf le 01/10, jour
    # oublié à la saisie ou vraie reprise. Signalé comme nouvel arrêt, il
    # ferait appliquer trois jours de carence à tort.
    arrets = {"e1": [_arret(date(2026, 9, 1), date(2026, 9, 30), date(2026, 10, 1)),
                     _arret(date(2026, 10, 2), date(2026, 10, 12), date(2026, 10, 1))]}
    (s,) = signalements_a_faire(arrets, [], depuis=date(2026, 10, 1), effectif=20)
    assert s.debut == date(2026, 10, 2)
    assert s.a_verifier == (
        "Un seul jour sans arrêt depuis le précédent, fini le 30/09/2026 : si c'est une "
        "prolongation, complétez l'arrêt au lieu de le signaler (sinon trois jours de "
        "carence seraient appliqués)."
    )


def test_un_arret_bien_apres_le_precedent_n_est_pas_a_verifier():
    arrets = {"e1": [_arret(date(2026, 9, 1), date(2026, 9, 20), date(2026, 9, 2)),
                     _arret(date(2026, 10, 5), date(2026, 10, 9), date(2026, 10, 6))]}
    (s,) = signalements_a_faire(arrets, [], depuis=date(2026, 10, 1), effectif=20)
    assert s.a_verifier is None
