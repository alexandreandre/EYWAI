"""Base-flip generalise: gere temps-plein (151.67), temps-partiel (toute duree
horaire) ET forfait-jour depuis la ligne SALAIRE DE BASE du bulletin.

Deux formes de bulletin Cegid, dans cet ordre de priorite :
  1. HEURES   : "SALAIRE DE BASE <heures> <taux4> [<montant>]" -> base = montant
                sinon heures x taux.
  2. FORFAIT  : "SALAIRE DE BASE" SANS heures ni taux (le forfait annuel remplace
                l'horaire, cf. ligne "Forfait NNN jours"). Le montant est SEUL,
                dans la colonne "Montant salarial" du PDF. Il n'est pas captable
                par un regex de fin de ligne : la barre laterale du bulletin
                ("SMIC Horaire :", "Plafond Secu :"...) atterrit frequemment sur
                la meme ligne texte (vrai des fevrier). On lit donc la POSITION
                des colonnes dans la ligne d'entete ("Rubriques ... Montant
                salarial ... Mt patronal") et on ne retient que le nombre dont la
                fin tombe dans la zone Montant salarial -- ce qui exclut par
                construction la colonne patronale et la barre laterale.

Sequentiel DB-only. Revert via mbc_dbsafe.py restore employees (salaire_de_base
est un champ PARTAGE entre tous les mois : TOUJOURS restaurer apres un flip).
Usage: flip_base_all.py <year> <month> [--dry] [MATRICULE...]"""
import sys, re
sys.path.insert(0, "/Users/alex/Desktop/EYWAI/EYWAI/backend")
from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
COMPANY = "Mont Blanc Composite"
YEAR = int(sys.argv[1]); MONTH = int(sys.argv[2])
DRY = "--dry" in sys.argv
wanted = set(a for a in sys.argv[3:] if not a.startswith("--"))
# "SALAIRE DE BASE  <heures>  <taux4>  [<montant>]"  (montant optionnel)
_RE = re.compile(r"SALAIRE DE BASE\s+(\d+\.\d{2})\s+(\d+\.\d{4})(?:\s+([\d\s]+\.\d{2}))?")
_NUM = re.compile(r"\d[\d ]*\.\d{2}")
_HDR = re.compile(r"Rubriques.*Montant salarial.*Mt patronal")


def _montant_salarial_zone(lines):
    """Bornes [debut, fin) de la colonne Montant salarial, lues dans l'entete."""
    for ln in lines:
        if _HDR.search(ln):
            return ln.index("Montant salarial"), ln.index("Mt patronal")
    return None


def parse_base_heures(text):
    m = _RE.search(text or "")
    if not m:
        return None
    hours = float(m.group(1)); rate = float(m.group(2))
    if m.group(3):
        return round(float(m.group(3).replace(" ", "")), 2)
    return round(hours * rate, 2)


def parse_base_forfait(text):
    """Base forfait-jour = seul nombre de la ligne SALAIRE DE BASE tombant dans la
    colonne Montant salarial. None si ambigu (jamais de valeur devinee)."""
    lines = (text or "").split("\n")
    zone = _montant_salarial_zone(lines)
    if zone is None:
        return None
    lo, hi = zone
    for ln in lines:
        if not ln.strip().startswith("SALAIRE DE BASE"):
            continue
        cands = [m for m in _NUM.finditer(ln) if lo < m.end() <= hi]
        if len(cands) != 1:
            return None
        return round(float(cands[0].group(0).replace(" ", "")), 2)
    return None


def parse_base(text):
    """Base mensuelle du bulletin, chemin heures d'abord puis repli forfait."""
    val = parse_base_heures(text)
    if val is not None:
        return val, "heures"
    val = parse_base_forfait(text)
    if val is not None:
        return val, "forfait"
    return None, None


admin = get_supabase_admin_client()
pdf = resolve_bulletin_pdf(COMPANY, YEAR, MONTH)
refs = load_reference_bulletins(COMPANY, YEAR, MONTH, pdf_path=pdf)
cid = resolve_company_id(COMPANY)
matched = match_employees(cid, refs).matched
if wanted:
    matched = [m for m in matched if m.matricule in wanted]
matched.sort(key=lambda m: m.matricule)
n = 0; skipped = []; n_forfait = 0
for m in matched:
    montant, how = parse_base(m.reference.raw_text or "")
    if montant is None:
        skipped.append(m.matricule); continue
    if how == "forfait":
        n_forfait += 1
    emp = admin.table("employees").select("salaire_de_base").eq("id", m.employee_id).single().execute().data
    cur = (emp.get("salaire_de_base") or {}).get("valeur")
    if DRY:
        print(f"  {m.matricule:16s} [{how:7s}] config={cur} -> bulletin={montant}")
    elif abs((cur or 0) - montant) > 0.005:
        newsb = dict(emp.get("salaire_de_base") or {"type": "mensuel"}); newsb["valeur"] = montant
        admin.table("employees").update({"salaire_de_base": newsb}).eq("id", m.employee_id).execute()
        n += 1
print(f"=== flip_base_all {MONTH:02d}: {n} flipped ({n_forfait} forfait lus), "
      f"{len(skipped)} skipped (no-hours): {skipped[:30]} ===")
