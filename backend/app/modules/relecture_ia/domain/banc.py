"""Bilan du banc d'essai : ce que la relecture retrouve, manque ou invente."""

from __future__ import annotations

from typing import Any

from app.modules.relecture_ia.domain.garde import normaliser_ligne


def bilan_du_banc(
    cas: list[dict[str, Any]], resultats: list[dict[str, Any]]
) -> dict[str, Any]:
    """`cas` : {bulletin, ligne} ; ligne nulle = bulletin juste, tout signalement est une fausse alerte.

    `resultats` : la relecture de chaque bulletin. Une erreur attendue sur un bulletin
    non relu est comptée manquée.
    """
    attendus: dict[str, set[str]] = {}
    for c in cas:
        lignes = attendus.setdefault(str(c["bulletin"]), set())
        if c.get("ligne"):
            lignes.add(normaliser_ligne(c["ligne"]))

    trouves: list[dict[str, str]] = []
    fausses_alertes: list[dict[str, str]] = []
    releves: set[tuple[str, str]] = set()
    for resultat in resultats:
        bulletin = str(resultat["payslip_id"])
        for signalement in resultat.get("signalements") or []:
            ligne = normaliser_ligne(signalement.get("ligne", ""))
            if ligne in attendus.get(bulletin, set()):
                releves.add((bulletin, ligne))
                trouves.append({"bulletin": bulletin, "ligne": ligne})
            else:
                fausses_alertes.append({"bulletin": bulletin, "ligne": ligne})

    manques = [
        {"bulletin": bulletin, "ligne": ligne}
        for bulletin, lignes in attendus.items()
        for ligne in sorted(lignes)
        if (bulletin, ligne) not in releves
    ]
    return {
        "trouves": trouves,
        "manques": manques,
        "fausses_alertes": fausses_alertes,
        "echecs": [
            {"bulletin": str(r["payslip_id"]), "message": r.get("message")}
            for r in resultats
            if r.get("statut") == "echec"
        ],
        "cout_usd": round(sum(float(r.get("cout_usd") or 0) for r in resultats), 4),
    }
