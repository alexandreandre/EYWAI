"""Refaire l'import d'un fichier déjà validé (Supabase moqué).

Constat du 03/10/2026 : après la correction du lecteur, deux salariés sautés sur
trois relevés déjà validés ont été rattrapés par un script, faute de pouvoir
relire le fichier depuis l'écran. Désormais :

- un fichier déjà importé est refusé avec le lot précédent (date, qui, combien)
  et la proposition « Refaire l'import de ce fichier » ;
- la relecture montre les jours corrigés à la main depuis le premier import ;
- l'enregistrement les garde, sauf ceux que la gestionnaire reprend du fichier ;
- le lot rejoué est un nouveau lot, lié à l'ancien.

Fixtures inventées : aucun salarié réel.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.application.timesheet_import import reimport_service
from app.modules.schedules.domain.corrections_a_la_main import ValeurJour
from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
)

pytestmark = pytest.mark.unit

_SERVICE = "app.modules.schedules.application.timesheet_import.reimport_service"


def _proposition(employes: list[tuple[str | None, list[AiDayEntry]]], **kw):
    return AiCalendarProposalResponse(
        year=kw.pop("year", 2026),
        month=kw.pop("month", 9),
        source="test",
        employees=[
            AiEmployeeProposal(
                raw_name=f"Salarié {i}",
                employee_id=eid,
                days=jours,
                review_status=kw.get("review_status", "ok"),
                match_confidence="high",
            )
            for i, (eid, jours) in enumerate(employes)
        ],
    )


def _jour(jour, heures, type_="travail", nature="reel", **kw):
    return AiDayEntry(jour=jour, heures=heures, type=type_, nature=nature, **kw)


def _lot_valide(**kw):
    lot = {
        "id": "lot-ancien",
        "company_id": "co-1",
        "status": "committed",
        "filename": "S39.pdf",
        "file_hash": "h39",
        "user_id": "rh-1",
        "completed_at": "2026-10-01T16:09:46.857669+00:00",
        "created_at": "2026-10-01T16:09:24+00:00",
        "summary_json": {"committed_days": 47},
        "preview_json": _proposition(
            [("emp-1", [_jour(15, 8.5), _jour(16, 8.5), _jour(19, None, "weekend")])]
        ).model_dump(mode="json"),
    }
    lot.update(kw)
    return lot


class TestJoursEcritsParLot:
    def test_ce_qu_a_ecrit_un_lot_valide_est_son_apercu_relu(self):
        lot = _lot_valide(
            preview_json=_proposition(
                [
                    ("emp-1", [_jour(15, 8.5), _jour(30, 7.0, year=2026, month=8)]),
                    (None, [_jour(15, 9.0)]),
                    ("emp-2", [_jour(15, 6.0, nature="prevu")]),
                ]
            ).model_dump(mode="json")
        )

        assert reimport_service.jours_ecrits_par_lot(lot) == {
            ("emp-1", 2026, 9, 15): ValeurJour(8.5, "travail"),
            ("emp-1", 2026, 8, 30): ValeurJour(7.0, "travail"),
        }

    def test_un_salarie_hors_de_l_enregistrement_n_a_rien_ecrit(self):
        lot = _lot_valide(
            preview_json=_proposition(
                [("emp-1", [_jour(15, 8.5)]), ("emp-2", [_jour(15, 7.0)])]
            ).model_dump(mode="json"),
            summary_json={"commit_request": {"employee_ids": ["emp-2"]}},
        )

        assert set(reimport_service.jours_ecrits_par_lot(lot)) == {("emp-2", 2026, 9, 15)}

    def test_une_ligne_non_identifiee_n_a_rien_ecrit(self):
        lot = _lot_valide(
            preview_json=_proposition(
                [("emp-1", [_jour(15, 8.5)])], review_status="error"
            ).model_dump(mode="json")
        )

        assert reimport_service.jours_ecrits_par_lot(lot) == {}

    def test_un_jour_garde_a_la_relecture_n_a_pas_ete_ecrit_par_ce_lot(self):
        lot = _lot_valide(
            summary_json={
                "corrections_gardees": [
                    {"employee_id": "emp-1", "annee": 2026, "mois": 9, "jour": 15}
                ]
            }
        )

        assert ("emp-1", 2026, 9, 15) not in reimport_service.jours_ecrits_par_lot(lot)

    def test_un_lot_sur_plusieurs_mois_a_ecrit_ses_groupes_de_mois(self):
        lot = _lot_valide(
            summary_json={
                "multi_month": True,
                "month_groups": [
                    {
                        "year": 2026,
                        "month": 8,
                        "employees": [
                            {
                                "employee_id": "emp-1",
                                "days": [
                                    {"jour": 31, "heures": 7.0, "type": "travail", "nature": "reel"}
                                ],
                            }
                        ],
                    }
                ],
            }
        )

        assert reimport_service.jours_ecrits_par_lot(lot) == {
            ("emp-1", 2026, 8, 31): ValeurJour(7.0, "travail")
        }


class TestDejaImporte:
    def _verifier(self, lots: dict[str, dict | None], *, refaire=False, nom="RH Démo"):
        with patch(f"{_SERVICE}.timesheet_import_repository") as repo:
            repo.lots_valides_du_fichier.side_effect = lambda co, h: (
                [lots[h]] if lots.get(h) else []
            )
            repo.nom_utilisateur.return_value = nom
            return reimport_service.verifier_import(
                "co-1",
                [(f"{h}.pdf", h) for h in lots],
                refaire_import=refaire,
            )

    def test_un_fichier_jamais_importe_passe(self):
        assert self._verifier({"h40": None}) == []

    def test_un_fichier_deja_importe_est_refuse_avec_le_lot_precedent(self):
        with pytest.raises(ScheduleAppError) as refus:
            self._verifier({"h39": _lot_valide()})

        erreur = refus.value
        assert erreur.status_code == 409
        assert erreur.detail["code"] == "deja_importe"
        (fichier,) = erreur.detail["fichiers"]
        assert fichier["filename"] == "h39.pdf"
        assert fichier["lot_precedent"] == {
            "batch_id": "lot-ancien",
            "fichier": "h39.pdf",
            "filename": "S39.pdf",
            "valide_le": "2026-10-01T16:09:46.857669+00:00",
            "valide_par": "RH Démo",
            "jours_ecrits": 47,
        }

    def test_le_refus_dit_quand_qui_et_quoi_faire_sans_jargon(self):
        with pytest.raises(ScheduleAppError) as refus:
            self._verifier({"h39": _lot_valide()})

        message = refus.value.message
        assert refus.value.detail["message"] == message
        assert "déjà été importé" in message
        # 16:09 UTC le 1er octobre = 18:09 à Paris.
        assert "le 01/10/2026 à 18:09 par RH Démo" in message
        assert "calendrier" in message
        assert "Refaire l'import de ce fichier" in message
        assert "hash" not in message and "batch" not in message

    def test_plusieurs_fichiers_deja_importes_sont_tous_nommes(self):
        with pytest.raises(ScheduleAppError) as refus:
            self._verifier(
                {"h38": _lot_valide(id="lot-38"), "h40": None, "h39": _lot_valide()}
            )

        noms = [f["filename"] for f in refus.value.detail["fichiers"]]
        assert noms == ["h38.pdf", "h39.pdf"]
        assert "Refaire l'import de ces fichiers" in refus.value.message

    def test_qui_reste_vide_si_le_profil_est_illisible(self):
        with pytest.raises(ScheduleAppError) as refus:
            self._verifier({"h39": _lot_valide()}, nom=None)

        assert refus.value.detail["fichiers"][0]["lot_precedent"]["valide_par"] is None
        assert "par None" not in refus.value.message
        assert "le 01/10/2026 à 18:09 :" in refus.value.message

    def test_refaire_l_import_rend_les_lots_precedents_sans_refuser(self):
        deja = self._verifier({"h39": _lot_valide(), "h40": None}, refaire=True)

        assert [(d["filename"], d["file_hash"]) for d in deja] == [("h39.pdf", "h39")]
        assert deja[0]["lot_precedent"]["batch_id"] == "lot-ancien"

    def test_le_lot_precedent_est_le_dernier_valide(self):
        with patch(f"{_SERVICE}.timesheet_import_repository") as repo:
            repo.lots_valides_du_fichier.return_value = [
                _lot_valide(id="lot-recent"),
                _lot_valide(id="lot-ancien"),
            ]
            lot = reimport_service.lot_precedent_du_fichier("co-1", "h39")

        assert lot["id"] == "lot-recent"


class TestAnnoterLaRelecture:
    def _annoter(self, proposition, *, reel_en_base, lot=None):
        deja = [
            {
                "filename": "S39.pdf",
                "file_hash": "h39",
                "lot_precedent": {
                    "batch_id": "lot-ancien",
                    "fichier": "S39.pdf",
                    "filename": "S39.pdf",
                    "valide_le": "2026-10-01T16:09:46+00:00",
                    "valide_par": "RH Démo",
                    "jours_ecrits": 47,
                },
            }
        ]
        with (
            patch(f"{_SERVICE}.timesheet_import_repository") as repo,
            patch(f"{_SERVICE}.schedule_repository") as calendriers,
        ):
            repo.get_batch.return_value = lot or _lot_valide()
            calendriers.list_schedules_for_employees.side_effect = (
                lambda ids, annee, mois: {
                    eid: {"actual_hours": {"calendrier_reel": reel}}
                    for (eid, a, m), reel in reel_en_base.items()
                    if eid in ids and (a, m) == (annee, mois)
                }
            )
            return reimport_service.annoter_reimport("co-1", proposition, deja)

    def test_la_relecture_porte_le_lot_precedent_et_les_corrections_a_la_main(self):
        proposition = _proposition([("emp-1", [_jour(15, 8.0), _jour(16, 8.0)])])

        annotee, resume = self._annoter(
            proposition,
            reel_en_base={
                ("emp-1", 2026, 9): [
                    {"jour": 15, "type": "travail", "heures_faites": 9.0},
                    {"jour": 16, "type": "travail", "heures_faites": 8.5},
                ]
            },
        )

        assert annotee.reimport is not None
        assert [lot.batch_id for lot in annotee.reimport.lots_precedents] == ["lot-ancien"]
        (correction,) = annotee.reimport.corrections_a_la_main
        assert (correction.employee_id, correction.jour) == ("emp-1", 15)
        assert correction.import_precedent.heures == 8.5
        assert correction.calendrier.heures == 9.0
        assert correction.fichier.heures == 8.0
        assert resume == {
            "reimport": True,
            "previous_committed_batch_id": "lot-ancien",
            "reimport_fichiers": [
                {
                    "filename": "S39.pdf",
                    "file_hash": "h39",
                    "previous_committed_batch_id": "lot-ancien",
                }
            ],
        }

    def test_un_salarie_saute_par_l_ancien_import_s_ecrit_sans_question(self):
        proposition = _proposition([("emp-9", [_jour(15, 8.0)])])

        annotee, _ = self._annoter(proposition, reel_en_base={})

        assert annotee.reimport.corrections_a_la_main == []

    def test_une_semaine_a_cheval_lit_le_calendrier_de_chaque_mois(self):
        proposition = _proposition(
            [("emp-1", [_jour(31, 8.0, year=2026, month=8), _jour(1, 8.0)])]
        )
        lot = _lot_valide(
            preview_json=_proposition(
                [("emp-1", [_jour(31, 7.0, year=2026, month=8), _jour(1, 7.0)])]
            ).model_dump(mode="json")
        )

        annotee, _ = self._annoter(
            proposition,
            lot=lot,
            reel_en_base={
                ("emp-1", 2026, 8): [{"jour": 31, "type": "travail", "heures_faites": 6.0}],
                ("emp-1", 2026, 9): [{"jour": 1, "type": "travail", "heures_faites": 7.0}],
            },
        )

        assert [
            (c.mois, c.jour) for c in annotee.reimport.corrections_a_la_main
        ] == [(8, 31)]


# ----- L'enregistrement d'une relecture -----

_COMMIT = "app.modules.schedules.application.timesheet_import.commit_service"


def _lot_relu(**summary):
    return {
        "id": "lot-relu",
        "company_id": "co-1",
        "status": "committing",
        "file_hash": "h39",
        "filename": "S39.pdf",
        "preview_json": _proposition(
            [("emp-1", [_jour(15, 8.0), _jour(16, 8.0), _jour(17, 8.0)])]
        ).model_dump(mode="json"),
        "summary_json": {
            "reimport": True,
            "previous_committed_batch_id": "lot-ancien",
            "reimport_fichiers": [
                {
                    "filename": "S39.pdf",
                    "file_hash": "h39",
                    "previous_committed_batch_id": "lot-ancien",
                }
            ],
            **summary,
        },
    }


def _lot_ancien():
    return _lot_valide(
        preview_json=_proposition(
            [("emp-1", [_jour(15, 8.5), _jour(16, 8.5), _jour(17, 8.0)])]
        ).model_dump(mode="json")
    )


def _calendrier_corrige():
    # 15 et 16 corrigés à la main (8,5 → 9), 17 intact.
    return {
        "emp-1": {
            "employee_id": "emp-1",
            "actual_hours": {
                "calendrier_reel": [
                    {"jour": 15, "type": "travail", "heures_faites": 9.0},
                    {"jour": 16, "type": "travail", "heures_faites": 9.0},
                    {"jour": 17, "type": "travail", "heures_faites": 8.0},
                ]
            },
        }
    }


def _enregistrer(lot_relu, *, calendrier=None):
    from unittest.mock import MagicMock

    from app.modules.schedules.application.timesheet_import.commit_service import (
        commit_batch_bulk,
    )
    from app.modules.schedules.schemas.timesheet_import import (
        TimesheetImportCommitRequest,
    )

    lots = {"lot-relu": lot_relu, "lot-ancien": _lot_ancien()}
    repo = MagicMock()
    repo.get_batch.side_effect = lambda batch_id, company_id=None: lots.get(batch_id)
    repo.lots_valides_du_fichier.return_value = [_lot_ancien()]
    repo.is_cancel_requested.return_value = False
    with (
        patch(f"{_COMMIT}.timesheet_import_repository", repo),
        patch(f"{_SERVICE}.timesheet_import_repository", repo),
        patch(f"{_COMMIT}.schedule_repository") as calendriers,
        patch(f"{_COMMIT}.get_employee_company_and_statut", return_value=("co-1", "CDI")),
        patch(f"{_COMMIT}._arrets_des_mois", return_value={}),
        patch(f"{_COMMIT}.record_schedule_import_run"),
    ):
        calendriers.list_schedules_for_employees.return_value = (
            calendrier if calendrier is not None else _calendrier_corrige()
        )
        resultat = commit_batch_bulk(
            "lot-relu", company_id="co-1", request=TimesheetImportCommitRequest()
        )
    return resultat, calendriers, repo


def _reel_ecrit(calendriers) -> dict[int, float | None]:
    (payloads,), _ = calendriers.bulk_upsert_schedules.call_args
    (payload,) = payloads
    return {
        d["jour"]: d["heures_faites"]
        for d in payload["actual_hours"]["calendrier_reel"]
    }


def _resume_final(repo) -> dict:
    return repo.update_batch.call_args_list[-1].args[1]["summary_json"]


class TestEnregistrerUneRelecture:
    def test_les_corrections_a_la_main_ne_sont_pas_reecrites(self):
        resultat, calendriers, repo = _enregistrer(_lot_relu())

        assert _reel_ecrit(calendriers) == {15: 9.0, 16: 9.0, 17: 8.0}
        assert resultat["total_days_written"] == 1
        assert [c["jour"] for c in resultat["corrections_gardees"]] == [15, 16]
        resume = _resume_final(repo)
        assert [c["jour"] for c in resume["corrections_gardees"]] == [15, 16]
        assert resume["committed_days"] == 1
        # Le lot rejoué pointe l'ancien.
        assert resume["previous_committed_batch_id"] == "lot-ancien"

    def test_la_garde_se_recalcule_contre_le_calendrier_du_moment(self):
        # Le 16 a été remis à 8,5 entre la revue et l'enregistrement.
        calendrier = _calendrier_corrige()
        calendrier["emp-1"]["actual_hours"]["calendrier_reel"][1]["heures_faites"] = 8.5

        resultat, calendriers, _ = _enregistrer(_lot_relu(), calendrier=calendrier)

        assert _reel_ecrit(calendriers) == {15: 9.0, 16: 8.0, 17: 8.0}
        assert [c["jour"] for c in resultat["corrections_gardees"]] == [15]

    def test_un_lot_de_reference_illisible_garde_tout_ce_qui_differe(self):
        resultat, _, _ = _enregistrer(
            _lot_relu(
                previous_committed_batch_id="lot-inconnu",
                reimport_fichiers=[
                    {"filename": "S39.pdf", "previous_committed_batch_id": "lot-inconnu"}
                ],
            )
        )

        # Rien de connu comme « écrit par l'import » : tout jour qui porte des
        # heures au calendrier et que le fichier contredit est gardé.
        assert [c["jour"] for c in resultat["corrections_gardees"]] == [15, 16]

    def test_un_import_ordinaire_ecrit_comme_avant(self):
        lot = _lot_relu()
        lot["summary_json"] = {}

        resultat, calendriers, _ = _enregistrer(lot)

        assert _reel_ecrit(calendriers) == {15: 8.0, 16: 8.0, 17: 8.0}
        assert "corrections_gardees" not in resultat

    def test_tout_garde_ne_fait_pas_echouer_l_enregistrement(self):
        lot = _lot_relu()
        lot["preview_json"] = _proposition([("emp-1", [_jour(15, 8.0)])]).model_dump(
            mode="json"
        )

        resultat, calendriers, _ = _enregistrer(lot)

        calendriers.bulk_upsert_schedules.assert_not_called()
        assert resultat["status"] == "committed"
        assert resultat["total_days_written"] == 0
        assert [c["jour"] for c in resultat["corrections_gardees"]] == [15]


class TestEnregistrerUnTableurSurPlusieursMois:
    def test_les_corrections_a_la_main_sont_gardees_aussi(self):
        lot = _lot_relu(
            multi_month=True,
            month_groups=[
                {
                    "year": 2026,
                    "month": 9,
                    "employees": [
                        {
                            "employee_id": "emp-1",
                            "raw_name": "Salarié 0",
                            "days": [
                                {"jour": j, "heures": 8.0, "type": "travail", "nature": "reel"}
                                for j in (15, 16, 17)
                            ],
                        }
                    ],
                }
            ],
        )
        with patch(
            f"{_COMMIT}.admin_repo.list_company_employees",
            return_value=[{"id": "emp-1", "company_id": "co-1"}],
        ):
            resultat, calendriers, repo = _enregistrer(lot)

        assert _reel_ecrit(calendriers) == {15: 9.0, 16: 9.0, 17: 8.0}
        assert [c["jour"] for c in resultat["corrections_gardees"]] == [15, 16]
        assert [c["jour"] for c in _resume_final(repo)["corrections_gardees"]] == [15, 16]

    def test_tout_garde_ne_fait_pas_echouer_l_enregistrement(self):
        lot = _lot_relu(
            multi_month=True,
            month_groups=[
                {
                    "year": 2026,
                    "month": 9,
                    "employees": [
                        {
                            "employee_id": "emp-1",
                            "days": [
                                {"jour": 15, "heures": 8.0, "type": "travail", "nature": "reel"}
                            ],
                        }
                    ],
                }
            ],
        )
        with patch(
            f"{_COMMIT}.admin_repo.list_company_employees",
            return_value=[{"id": "emp-1", "company_id": "co-1"}],
        ):
            resultat, calendriers, _ = _enregistrer(lot)

        calendriers.bulk_upsert_schedules.assert_not_called()
        assert resultat["status"] == "committed"
        assert [c["jour"] for c in resultat["corrections_gardees"]] == [15]
