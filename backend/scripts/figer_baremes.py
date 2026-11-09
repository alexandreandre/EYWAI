"""Fige les barèmes de l'année qui se termine, avant de poser ceux de janvier (R-229).

Usage, depuis backend/, PYTHONPATH=. :
    python scripts/figer_baremes.py 2026            simulation, n'écrit rien
    python scripts/figer_baremes.py 2026 --ecrire   écrit la ligne baremes_figes_2026

À lancer avant toute pose de barèmes de la nouvelle année. Écrit une ligne active de
`payroll_config` (clé `baremes_figes_<année>`), sans toucher aux barèmes actifs. Un
bulletin de cette année régénéré ensuite se recalcule avec ces valeurs.
"""
from __future__ import annotations

import sys

#: Le versement mobilité dépend de la commune et pèse 99 % des barèmes ; le reste n'est pas un barème.
CLES_EXCLUES = {"taux_vmrr", "payslip_edit_lock"}


def contenu_a_figer(lignes: list[dict], annee: int) -> dict:
    """Les barèmes actifs à figer ; refuse s'ils ne sont pas ceux de `annee`."""
    contenu = {
        l["config_key"]: l["config_data"]
        for l in lignes
        if l["config_key"] not in CLES_EXCLUES and not l["config_key"].startswith("baremes_figes_")
    }
    for cle in ("smic", "reduction_generale"):
        trouvee = (contenu.get(cle) or {}).get("annee")
        if int(trouvee or 0) != annee:
            raise SystemExit(f"{cle} porte l'année {trouvee}, pas {annee} : rien n'est figé.")
    return contenu


def main() -> None:
    annee = int(sys.argv[1])
    ecrire = "--ecrire" in sys.argv
    from app.core.database import get_supabase_admin_client

    client = get_supabase_admin_client()
    cle = f"baremes_figes_{annee}"
    lignes = (
        client.table("payroll_config")
        .select("config_key, config_data")
        .eq("is_active", True)
        .is_("company_id", "null")
        .execute()
        .data
    )
    if any(l["config_key"] == cle for l in lignes):
        raise SystemExit(f"{cle} existe déjà : rien n'est écrit.")
    contenu = contenu_a_figer(lignes, annee)
    print(f"{cle} : {len(contenu)} barèmes : {', '.join(sorted(contenu))}")
    if not ecrire:
        print("Simulation : rien n'est écrit (--ecrire pour écrire).")
        return
    client.table("payroll_config").insert(
        {
            "config_key": cle,
            "config_data": contenu,
            "version": 1,
            "is_active": True,
            "comment": f"Barèmes de {annee} figés avant la pose de ceux de {annee + 1}",
        }
    ).execute()
    print("Écrit.")


if __name__ == "__main__":
    main()
