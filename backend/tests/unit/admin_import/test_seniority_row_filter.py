"""Tests filtre lignes notes Excel — import ancienneté."""


from app.modules.admin_import.application.seniority_row_filter import (
    should_skip_seniority_row,
)


class TestShouldSkipSeniorityRow:
    def test_skips_instruction_cadres(self):
        assert should_skip_seniority_row(
            first_name="",
            last_name="les cadres n'ont pas de prime d'ancienneté",
            full_name="",
            identity="les cadres n'ont pas de prime d'ancienneté",
            matricule="",
        )

    def test_skips_instruction_maladie(self):
        assert should_skip_seniority_row(
            first_name="",
            last_name=(
                "Pour les personnes en arrêt de travail maladie / AT il faut payer "
                "la prime d'ancienneté de base (151h67) SI et SEULEMENT SI il y a "
                "un maintien de salaire"
            ),
            full_name="",
            identity="",
            matricule="",
        )

    def test_keeps_real_employee(self):
        assert not should_skip_seniority_row(
            first_name="Francine",
            last_name="BOURMAULT",
            full_name="",
            identity="Francine BOURMAULT",
            matricule="",
        )

    def test_keeps_compound_last_name(self):
        assert not should_skip_seniority_row(
            first_name="Serge",
            last_name="BUZISA LUSELA",
            full_name="",
            identity="Serge BUZISA LUSELA",
            matricule="",
        )

    def test_skips_empty_row(self):
        assert should_skip_seniority_row(
            first_name="",
            last_name="",
            full_name="",
            identity="",
            matricule="",
        )

    def test_keeps_row_with_seniority_comment_column(self):
        """Commentaire salarié « Reprise ancienneté… » ne doit pas filtrer la ligne."""
        assert not should_skip_seniority_row(
            first_name="Francisco",
            last_name="MIRANDA",
            full_name="",
            identity="Francisco MIRANDA",
            matricule="",
            row={
                "NOM": "MIRANDA",
                "PRENOM": "Francisco",
                "Date ancienneté": "1/1/2009",
                "Commentaire": "Reprise ancienneté dernier contrat (autre société)",
            },
        )
