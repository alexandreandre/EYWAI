"""Lot 4 Task 1 : plus jamais une heure de pause fantôme sur les imports.

La pause est l'affaire du serveur : l'IA rend les heures BRUTES, le
serveur recalcule toujours depuis DEBUT/FIN selon le réglage société —
et sans réglage, il ne déduit RIEN et le signale.
"""

from app.modules.schedules.application.handwritten_weekly import (
    calculate_hours_from_range,
    normalize_handwritten_weekly_payload,
)


def _jour(debut="07:00", fin="16:00", heures=8.0):
    return {
        "weekday": "lundi",
        "debut": debut,
        "fin": fin,
        "heures": heures,
        "type": "travail",
    }


def _payload(**jour_kwargs):
    return {
        "employees": [
            {"raw_name": "HUGO", "week_number": 18, "days": [_jour(**jour_kwargs)]}
        ]
    }


def test_sans_parametrage_aucune_pause_n_est_deduite():
    """07:00-16:00 = 9 h brutes. L'ancien repli déduisait 1 h en dur."""
    assert calculate_hours_from_range("07:00", "16:00", settings=None) == 9.0


def test_sans_parametrage_le_serveur_ecrase_l_heure_ia():
    """L'IA a rendu 8.0 (elle déduisait sa pause) : le serveur recalcule
    TOUJOURS depuis DEBUT/FIN — 9 h brutes, plus d'heure fantôme."""
    normalized = normalize_handwritten_weekly_payload(
        _payload(), year=2026, month=5
    )
    assert normalized["employees"][0]["days"][0]["heures"] == 9.0


def test_sans_parametrage_le_signal_remonte():
    avertissements: list = []
    normalize_handwritten_weekly_payload(
        _payload(), year=2026, month=5, warnings=avertissements
    )
    assert any(w.get("code") == "pause_non_parametree" for w in avertissements)


def test_sans_plage_horaire_l_heure_ia_est_conservee():
    """Pas de DEBUT/FIN lisibles : on garde ce que l'IA a pu lire."""
    normalized = normalize_handwritten_weekly_payload(
        _payload(debut=None, fin=None, heures=7.5), year=2026, month=5
    )
    assert normalized["employees"][0]["days"][0]["heures"] == 7.5


def test_le_prompt_ne_demande_plus_de_deduire_une_pause():
    from app.modules.schedules.application.timesheet_page_schema import (
        build_page_system_prompt,
    )

    prompt = build_page_system_prompt(year=2026, month=5, channel="vision")
    assert "déduire ~1 h" not in prompt
    assert "pause" not in prompt.lower() or "sans déduire" in prompt.lower()


def test_la_version_des_regles_de_calcul_a_ete_incrementee():
    """Piège documenté : l'empreinte de cache des aperçus ignore le prompt —
    sans bump, les aperçus resserviraient l'ancien calcul."""
    from app.modules.schedules.application.punch_accounting_service import (
        PUNCH_CALC_RULES_VERSION,
    )

    assert PUNCH_CALC_RULES_VERSION >= 3


def test_le_signal_atteint_les_warnings_du_consensus():
    """Le signal doit traverser le VRAI chemin d'import (consensus de page),
    pas seulement exister dans la fonction de normalisation — et survivre au
    filtre anti-bruit."""
    from app.modules.schedules.application.timesheet_page_consensus import (
        build_page_consensus,
    )

    payload = {
        "employees": [
            {
                "raw_name": "HUGO",
                "week_number": 18,
                "days": [
                    {"weekday": "lundi", "debut": "07:00", "fin": "16:00",
                     "heures": 8.0, "type": "travail"}
                ],
            }
        ],
        "confidence": 0.9,
    }
    result = build_page_consensus(
        vision_data=payload,
        text_data=None,
        format_hint="handwritten_weekly",
        year=2026,
        month=5,
        punch_settings=None,
        page_index=1,
    )
    assert any("paramétrage de pause" in w for w in result.warnings), result.warnings
