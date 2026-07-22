"""Tests contrôles convention collective en paie."""

from __future__ import annotations

from types import SimpleNamespace

from app.modules.payroll.engine.controles_convention import (
    controle_convention_collective,
    extraire_alertes_rh_depuis_bulletin,
)


def _contexte(
    *,
    idcc: str = "1486",
    coeff: float | None = 275,
    brut: float = 2500.0,
    regles: dict | None = None,
    libelle: str = "Syntec",
):
    return SimpleNamespace(
        is_alternant=False,
        contrat={
            "remuneration": {
                "convention_collective": {
                    "idcc": idcc,
                    "libelle": libelle,
                },
                "classification_conventionnelle": (
                    {"coefficient": coeff} if coeff is not None else None
                ),
            }
        },
        entreprise={"adresse_code_postal": "75001"},
        baremes={
            "conventions_collectives": {
                f"idcc_{idcc}": regles
                or {
                    "salaires_minima": [
                        {"coefficient": 275, "valeur": 2800.0, "libelle": "Agent de maîtrise"}
                    ]
                }
            }
        },
    )


class TestControlesConvention:
    def test_salaire_sous_minimum_alerte_critique(self):
        alertes = controle_convention_collective(_contexte(brut=2500.0), 2500.0)
        assert len(alertes) == 1
        assert alertes[0]["code"] == "cc_salaire_sous_minimum"
        assert alertes[0]["critique"] is True

    def test_salaire_conforme_pas_alerte(self):
        assert controle_convention_collective(_contexte(brut=2900.0), 2900.0) == []

    def test_minimum_compare_salaire_contractuel_avant_absences(self):
        ctx = _contexte(
            idcc="0292",
            libelle="IDCC 0292",
            coeff=710,
            regles={
                "salaires_minima": [{"coefficient": 710, "valeur": 1741.0}]
            },
        )
        ctx.contrat["remuneration"]["salaire_de_base"] = {"valeur": 1956.94}

        # Le brut du mois est réduit par des absences, mais le salaire
        # contractuel à temps plein reste supérieur au minimum conventionnel.
        assert controle_convention_collective(ctx, 953.78) == []

    def test_regles_absentes(self):
        ctx = _contexte(regles={})
        ctx.baremes = {"conventions_collectives": {}}
        alertes = controle_convention_collective(ctx, 3000.0)
        assert alertes[0]["code"] == "cc_regles_absentes"

    def test_extraire_alertes_depuis_bulletin(self):
        data = {
            "alertes_baremes": [
                {
                    "code": "cc_salaire_sous_minimum",
                    "critique": True,
                    "message": "Sous le minimum.",
                }
            ],
            "synthese_net": {"alertes_maintien": ["Règle légale appliquée"]},
        }
        out = extraire_alertes_rh_depuis_bulletin(data)
        assert len(out) == 2
        assert out[0]["severite"] == "bloquant"

    def test_metallurgie_position_coefficient_utilise_classe_emploi(self):
        """Coeff. position 710 + classe 7 → contrôle SMH sur la classe."""
        ctx = _contexte(
            idcc="3248",
            libelle="Métallurgie",
            coeff=710,
            regles={
                "grilles_salaires": [
                    {
                        "zone_type": "national",
                        "minima": [
                            {
                                "coefficient": 7,
                                "valeur": 2200.0,
                                "libelle": "Groupe D — Classe 7",
                            }
                        ],
                    }
                ]
            },
        )
        ctx.contrat["remuneration"]["classification_conventionnelle"] = {
            "groupe_emploi": "D",
            "classe_emploi": 7,
            "coefficient": 710,
        }
        assert controle_convention_collective(ctx, 2500.0) == []

    def test_metallurgie_smh_ne_se_controle_pas_sur_le_seul_salaire_mensuel(self):
        """Le SMH est annuel et inclut les éléments bruts éligibles de l'année."""
        ctx = _contexte(
            idcc="3248",
            libelle="Métallurgie",
            coeff=3,
            regles={
                "grilles_salaires": [
                    {
                        "zone_type": "national",
                        "minima": [
                            {
                                "coefficient": 3,
                                "valeur": 1892.50,
                                "libelle": "Groupe B — Classe 3",
                            }
                        ],
                    }
                ]
            },
        )
        ctx.contrat["remuneration"]["classification_conventionnelle"] = {
            "groupe_emploi": "B",
            "classe_emploi": 3,
        }
        ctx.contrat["remuneration"]["salaire_de_base"] = {"valeur": 1867.06}

        assert controle_convention_collective(ctx, 1900.0) == []

    def test_apprentissage_contractuel_ignore_le_controle_smh_avant_date_effet(self):
        ctx = _contexte(idcc="3248", libelle="Métallurgie", coeff=None)
        ctx.type_contrat = "Apprentissage"
        ctx.is_alternant = False

        assert controle_convention_collective(ctx, 1823.07) == []

    def test_metallurgie_position_sans_classe_alerte_explicite(self):
        ctx = _contexte(idcc="3248", libelle="Métallurgie", coeff=710, regles={})
        ctx.baremes = {
            "conventions_collectives": {
                "idcc_3248": {
                    "grilles_salaires": [
                        {
                            "zone_type": "national",
                            "minima": [{"coefficient": 7, "valeur": 2200.0}],
                        }
                    ]
                }
            }
        }
        ctx.contrat["remuneration"]["classification_conventionnelle"] = {
            "coefficient": 710,
        }
        alertes = controle_convention_collective(ctx, 2500.0)
        assert alertes[0]["code"] == "cc_coefficient_hors_grille"
        assert "classe d'emploi" in alertes[0]["message"].lower()
        assert "710" in alertes[0]["message"]


class TestControleNetSuperieurBrut:
    def test_alerte_si_net_superieur_brut(self):
        from app.modules.payroll.engine.controles_convention import (
            controle_net_superieur_brut,
        )

        alertes = controle_net_superieur_brut(1500.0, 1600.0)
        assert len(alertes) == 1
        assert alertes[0]["code"] == "net_superieur_brut"
        assert alertes[0]["critique"] is False

    def test_pas_alerte_si_net_inferieur_brut(self):
        from app.modules.payroll.engine.controles_convention import (
            controle_net_superieur_brut,
        )

        assert controle_net_superieur_brut(2000.0, 1800.0) == []

    def test_messages_liste_masquent_les_informations_non_actionnables(self):
        from app.modules.payroll.engine.controles_convention import (
            extraire_messages_alertes_rh,
        )

        messages = extraire_messages_alertes_rh(
            {
                "alertes_baremes": [
                    {
                        "code": "prime_anciennete_non_applicable_cadre",
                        "message": "Prime non applicable aux cadres.",
                        "critique": False,
                    },
                    {
                        "code": "prime_anciennete_prorata_zero",
                        "message": "Prime nulle sans temps retenu.",
                        "critique": False,
                    },
                ],
                "synthese_net": {
                    "alertes_maintien": [
                        "Ancienneté insuffisante pour le maintien légal",
                        "IJSS versées directement au salarié",
                        "Subrogation demandée sans maintien applicable — vérifier la cohérence",
                    ]
                },
            }
        )

        assert messages == [
            "Subrogation demandée sans maintien applicable — vérifier la cohérence"
        ]

    def test_extraire_messages_legacy_sans_alertes_baremes(self):
        from app.modules.payroll.engine.controles_convention import (
            extraire_messages_alertes_rh,
        )

        messages = extraire_messages_alertes_rh(
            {"salaire_brut": 1000.0, "net_a_payer": 1100.0}
        )
        assert messages == ["Net > Brut"]

    def test_minimum_prorata_temps_partiel(self):
        from types import SimpleNamespace

        ctx = SimpleNamespace(
            is_alternant=False,
            contrat={
                "contrat": {"temps_travail": {"duree_hebdomadaire": 15}},
                "remuneration": {
                    "convention_collective": {"idcc": "3248", "libelle": "Métallurgie"},
                    "classification_conventionnelle": {
                        "classe_emploi": 1,
                        "coefficient": 710,
                    },
                },
            },
            entreprise={"adresse_code_postal": "77420"},
            baremes={
                "conventions_collectives": {
                    "idcc_3248": {
                        "grilles_salaires": [
                            {
                                "zone_type": "national",
                                "minima": [
                                    {
                                        "coefficient": 1,
                                        "valeur": 1808.33,
                                        "libelle": "Groupe A — Classe 1",
                                    }
                                ],
                            }
                        ]
                    }
                }
            },
        )
        # 912 € > 1808.33 * 15/35 ≈ 775 €
        assert controle_convention_collective(ctx, 912.0) == []
