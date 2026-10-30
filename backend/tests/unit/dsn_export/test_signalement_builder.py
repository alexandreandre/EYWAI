from datetime import date

import pytest

from app.modules.dsn_export.application.builder import DsnBuildError
from app.modules.dsn_export.application.signalement_builder import construire_signalement
from app.modules.dsn_export.domain.settings import DsnSettings
from app.modules.dsn_export.domain.signalements import SignalementAFaire

SOCIETE = {"siret": "80248516900011", "name": "Société test", "code_naf": "2229A",
           "address": {"rue": "1 rue du Test", "code_postal": "01100", "ville": "OYONNAX"}}
SALARIE = {"nir": "1900101234567", "last_name": "Testeur", "first_name": "Alix",
           "date_naissance": "1990-01-15", "hire_date": "2026-09-01", "matricule": "42",
           "classification_conventionnelle": {"numero_contrat_dsn": "00042"}}
REGLAGES = DsnSettings(versements=[{"organisme": "URSSAF", "iban": "FR7612345678901234567890123", "bic": "TESTFRPP"}])


def _signalement(nature="04", motif="01", subrogation=False, reprise=None):
    return SignalementAFaire("e1", nature, motif, date(2026, 10, 5), date(2026, 10, 16), subrogation,
                             date(2026, 10, 6), date(2026, 10, 11), reprise)


def _lignes(texte):
    return dict(l.split(",", 1) for l in texte.strip().splitlines())


def test_un_signalement_d_arret_maladie():
    r = _lignes(construire_signalement(SOCIETE, SALARIE, _signalement(), settings=REGLAGES,
                                       essai=True, constitue_le=date(2026, 10, 7)))
    assert r["S10.G00.00.005"] == "'01'"
    assert r["S20.G00.05.001"] == "'04'"
    assert r["S20.G00.05.007"] == "'07102026'"
    assert "S20.G00.05.005" not in r and "S21.G00.06.003" not in r
    assert r["S21.G00.30.001"] == "'1900101234567'" and r["S21.G00.30.002"] == "'TESTEUR'"
    assert r["S21.G00.40.009"] == "'00042'" and "S21.G00.40.007" not in r
    assert (r["S21.G00.60.001"], r["S21.G00.60.002"], r["S21.G00.60.003"], r["S21.G00.60.004"]) == (
        "'01'", "'04102026'", "'16102026'", "'02'")
    assert "S21.G00.60.012" not in r
    assert r["S90.G00.90.002"] == "'1'"


def test_un_accident_du_travail_porte_la_date_de_l_accident():
    r = _lignes(construire_signalement(SOCIETE, SALARIE, _signalement(motif="06"), settings=REGLAGES,
                                       essai=True, constitue_le=date(2026, 10, 7)))
    assert r["S21.G00.60.002"] == "'05102026'" and r["S21.G00.60.012"] == "'05102026'"


def test_la_subrogation_porte_les_dates_et_le_compte_de_l_employeur():
    r = _lignes(construire_signalement(SOCIETE, SALARIE, _signalement(subrogation=True), settings=REGLAGES,
                                       essai=True, constitue_le=date(2026, 10, 7)))
    assert (r["S21.G00.60.004"], r["S21.G00.60.005"], r["S21.G00.60.006"]) == ("'01'", "'05102026'", "'16102026'")
    assert r["S21.G00.60.007"] == "'FR7612345678901234567890123'" and r["S21.G00.60.008"] == "'TESTFRPP'"


def test_une_subrogation_sans_iban_ne_se_genere_pas():
    with pytest.raises(DsnBuildError, match="IBAN"):
        construire_signalement(SOCIETE, SALARIE, _signalement(subrogation=True), settings=DsnSettings(),
                               essai=True, constitue_le=date(2026, 10, 7))


def test_une_reprise_porte_sa_date_sans_subrogation():
    r = _lignes(construire_signalement(SOCIETE, SALARIE, _signalement(nature="05", subrogation=True, reprise=date(2026, 10, 10)),
                                       settings=REGLAGES, essai=False, constitue_le=date(2026, 10, 12)))
    assert r["S20.G00.05.001"] == "'05'" and r["S10.G00.00.005"] == "'02'"
    assert (r["S21.G00.60.010"], r["S21.G00.60.011"]) == ("'10102026'", "'01'")
    assert "S21.G00.60.004" not in r


@pytest.mark.parametrize("champ", ["nir", "date_naissance", "hire_date", "first_name"])
def test_un_champ_d_identite_manquant_arrete_tout(champ):
    with pytest.raises(DsnBuildError):
        construire_signalement(SOCIETE, {**SALARIE, champ: None}, _signalement(), settings=REGLAGES,
                               essai=True, constitue_le=date(2026, 10, 7))
