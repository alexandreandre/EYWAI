"""L'aperçu d'un signalement : le vrai fichier lu en clair, NIR masqué.

Données fictives uniquement.
"""

from datetime import date

from app.modules.dsn_export.application.signalement_builder import construire_signalement
from app.modules.dsn_export.domain.apercu_signalement import (
    apercu,
    brut_masque,
    lire_blocs,
    masquer_nir,
)
from app.modules.dsn_export.domain.libelles_rubriques import BLOCS, RUBRIQUES
from app.modules.dsn_export.domain.settings import ContactDeclaration, DsnSettings
from app.modules.dsn_export.domain.signalements import SignalementAFaire
from app.modules.dsn_export.domain.usages_signalement import PERMISES

SOCIETE = {"siret": "80248516900011", "name": "Société Exemple", "code_naf": "2229A",
           "address": {"rue": "1 rue de l'Exemple", "code_postal": "01100", "ville": "VILLE"}}
NIR = "1900101234567"
SALARIE = {"nir": NIR, "last_name": "Dupont", "first_name": "Jean",
           "date_naissance": "1990-01-15", "hire_date": "2026-09-01", "matricule": "42",
           "classification_conventionnelle": {"numero_contrat_dsn": "00042"}}
REGLAGES = DsnSettings(
    versements=[{"organisme": "URSSAF", "iban": "FR7612345678901234567890123", "bic": "TESTFRPP"}],
    contacts_declaration=[ContactDeclaration(nom="CONTACT PAIE", telephone="0400000000",
                                             email="paie@exemple.fr", code_destinataire="01")],
)


def _arret(nature="04", subrogation=False, reprise=None):
    s = SignalementAFaire("e1", nature, "01", date(2026, 10, 5), date(2026, 10, 16), subrogation,
                          date(2026, 10, 6), date(2026, 10, 11), reprise)
    return construire_signalement(SOCIETE, SALARIE, s, settings=REGLAGES, essai=False,
                                  constitue_le=date(2026, 10, 7))


def _rubrique(resultat, code):
    return next(r for b in resultat["blocs"] for r in b["rubriques"] if r["code"] == code)


def test_le_nir_garde_ses_deux_premiers_et_deux_derniers_chiffres():
    assert masquer_nir(NIR) == "19•••••••••67"
    assert len(masquer_nir(NIR)) == len(NIR)
    assert masquer_nir("123") == "•••"


def test_l_arret_se_lit_par_bloc_dans_l_ordre_du_fichier():
    resultat = apercu(_arret(), nature="04", essai=False)
    parties = [b["partie"] for b in resultat["blocs"]]
    # Envoi, déclarant, entreprise, salarié, contrat, événement, puis le total.
    ordre = [p for i, p in enumerate(parties) if i == 0 or parties[i - 1] != p]
    assert ordre == ["envoi", "declarant", "entreprise", "salarie", "contrat", "evenement", "envoi"]
    (arret,) = [b for b in resultat["blocs"] if b["code"] == "S21.G00.60"]
    assert arret["libelle"] == "Arrêt de travail"
    motif = _rubrique(resultat, "S21.G00.60.001")
    assert motif == {"code": "S21.G00.60.001", "libelle": "Motif de l'arrêt", "valeur": "01",
                     "traduction": "maladie"}
    assert _rubrique(resultat, "S21.G00.60.004")["traduction"] == "non"
    assert _rubrique(resultat, "S20.G00.05.001")["traduction"] == "Signalement Arrêt de travail"
    assert _rubrique(resultat, "S10.G00.00.005")["traduction"] == "envoi fichier réel"
    assert resultat["libelle_nature"] == "Signalement d'arrêt de travail"


def test_le_nir_n_apparait_jamais_en_entier():
    texte = _arret()
    resultat = apercu(texte, nature="04", essai=False)
    assert _rubrique(resultat, "S21.G00.30.001")["valeur"] == "19•••••••••67"
    assert NIR not in str(resultat)
    # Le brut est le texte exact du fichier, à la seule valeur du NIR près.
    assert resultat["brut"] == texte.replace(f"'{NIR}'", "'19•••••••••67'")
    assert resultat["brut"].count("\r\n") == texte.count("\r\n")


def test_la_reprise_dit_sa_date_et_son_motif():
    resultat = apercu(_arret(nature="05", reprise=date(2026, 10, 12)), nature="05", essai=False)
    assert _rubrique(resultat, "S21.G00.60.010")["valeur"] == "12102026"
    assert _rubrique(resultat, "S21.G00.60.011")["traduction"] == "reprise normale"


def test_la_fin_de_contrat_traduit_le_motif_de_rupture():
    texte = "\r\n".join([
        "S20.G00.05.001,'07'",
        "S21.G00.30.001,'1900101234567'",
        "S21.G00.52.001,'011'", "S21.G00.52.002,'120.00'",
        "S21.G00.62.001,'31102026'", "S21.G00.62.002,'031'",
        "S21.G00.63.001,'90'",
    ]) + "\r\n"
    resultat = apercu(texte, nature="07", essai=False)
    assert _rubrique(resultat, "S21.G00.62.002")["traduction"] == (
        "fin de contrat à durée déterminée ou fin d'accueil occasionnel")
    assert _rubrique(resultat, "S21.G00.52.001")["traduction"] == "Indemnité légale de fin de CDD"
    assert _rubrique(resultat, "S21.G00.63.001")["traduction"] == "pas de clause de préavis applicable"
    assert [b["partie"] for b in resultat["blocs"]] == [
        "declarant", "salarie", "remuneration", "evenement", "evenement"]


def test_un_bloc_repete_se_lit_en_deux_blocs():
    blocs = lire_blocs("S21.G00.81.001,'076'\nS21.G00.81.004,'1.00'\nS21.G00.81.001,'100'\n")
    assert [len(b["rubriques"]) for b in blocs] == [2, 1]
    assert blocs[0]["libelle"] == "Cotisation individuelle"


def test_le_brut_sans_nir_reste_identique():
    texte = "S10.G00.00.001,'Martine'\r\nS20.G00.05.001,'04'\r\n"
    assert brut_masque(texte) == texte


def test_chaque_rubrique_d_un_signalement_a_son_libelle():
    rubriques = set().union(*PERMISES.values())
    assert not [c for c in rubriques if not RUBRIQUES.get(c)]
    assert not [c[:10] for c in rubriques if not BLOCS.get(c[:10])]
