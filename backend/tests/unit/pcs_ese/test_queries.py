"""La proposition vue par l'écran : collègues triés, salarié exclu, référentiel pour la liste."""

from app.modules.pcs_ese.application.queries import (
    proposition_en_dict,
    proposition_pour,
    referentiel_pour_ecran,
)
from app.modules.pcs_ese.domain.proposition import FicheCollegue


def fiche(eid, cid, code, poste="Agent de production", statut="Non-Cadre", soc=None):
    return FicheCollegue(eid, cid, soc or f"Société {cid}", poste, statut, code)


FICHES = [
    fiche("moi", "c1", "9999"),
    fiche("1", "c2", "674a", soc="Comitech"),
    fiche("2", "c1", "9999"),
]


def test_proposition_pour_le_salarie_lui_meme_exclu():
    p = proposition_pour("c1", "agent de production", "Non-Cadre", employee_id="moi", fiches=FICHES)
    assert (p.code, p.regle, p.nb_collegues) == ("674a", "b", 1)


def test_proposition_en_dict_pour_l_ecran():
    d = proposition_en_dict(proposition_pour("c1", "Agent de production", "Non-Cadre", fiches=FICHES))
    assert d["code"] == "674a" and d["sur"] is True
    assert d["candidats"][0] == {
        "code": "674a",
        "libelle": "Ouvriers de production non qualifiés : chimie, pharmacie, plasturgie",
        "raison": "Même poste et même statut qu'1 collègue du groupe (Comitech), en 674a.",
        "ecap": False,
    }


def test_referentiel_pour_ecran():
    lignes = referentiel_pour_ecran()
    assert len(lignes) == 430
    assert lignes[-1]["code"] == "9999"
    ligne = next(x for x in lignes if x["code"] == "543g")
    assert set(ligne) == {"code", "libelle", "metiers", "ecap", "public"}
    assert "Dessinateur détaillant" in ligne["metiers"]
