"""Réconciliateur auto-vérifiant — backtest paie MBC mai 2026.

Pour chaque salarié :
  1. Parse INTÉGRALEMENT le bulletin réel (primes, participation, acomptes,
     prêts, cantine, JTC, congés payés, mutuelle, prévoyance, date ancienneté,
     taux PAS, saisies/virements de trésorerie).
  2. Diffe contre l'état DB courant.
  3. Snapshot → applique → régénère → compare le tier-S.
     Garde si ça s'améliore, REVERT AUTOMATIQUEMENT si ça empire.

Respecte la discipline « ne jamais laisser un salarié pire, vérifier à chaque
fois » — mais sans intervention manuelle : les 74 en un passage surveillé.

Usage (depuis backend/) :
    .venv/bin/python -m scripts.backtest.mbc_reconcile [MATRICULE ...]
    (sans argument : tous les salariés matchés non convergés)
"""

from __future__ import annotations

import calendar
import copy
import datetime
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.backtest_company_payroll import _generate_payslip, compare_matches
from app.modules.payroll.backtest.thresholds import default_thresholds
from app.modules.payroll.documents.payslip_generator import (
    _is_frais_pro_non_soumis_input,
)

# --- Accélération backtest : le réconciliateur ne compare que des CHIFFRES, le
# rendu PDF (weasyprint) et l'upload storage ne servent à rien ici et coûtent
# l'essentiel du temps (~10x). Même stub que scripts/backtest/measure_par.py.
import weasyprint as _wp


def _pdf_stub(self, target=None, *a, **k):
    if target is None:
        return b"%PDF-1.4\n%stub\n"
    if hasattr(target, "write"):
        target.write(b"%PDF-1.4\n%stub\n")
        return None
    open(target, "wb").write(b"%PDF-1.4\n%stub\n")
    return None


_wp.HTML.write_pdf = _pdf_stub
import app.modules.payroll.documents.payslip_generator as _pg


class _FakeBucket:
    def upload(self, *a, **k):
        return None

    def create_signed_url(self, *a, **k):
        return {"signedURL": "stub"}


try:
    _pg.supabase.storage.from_ = lambda *a, **k: _FakeBucket()
except Exception:
    pass
import app.modules.employee_loans.application.payroll_integration as _pi

_pi.enrich_payslip_after_upsert = lambda data, *a, **k: data

COMPANY = "Mont Blanc Composite"
YEAR, MONTH = 2026, 5
# Mois cible paramétrable : « --month M [--year Y] » (défaut : mai 2026, le mois
# de référence historique). Indispensable pour passer le réconciliateur
# revert-safe sur les mois historiques — ⚠ flipper la base du mois AVANT
# (flip_base_all.py) puis restaurer après (mbc_dbsafe.py restore employees) :
# salaire_de_base est un champ PARTAGÉ entre tous les mois.
if "--month" in sys.argv:
    MONTH = int(sys.argv[sys.argv.index("--month") + 1])
if "--year" in sys.argv:
    YEAR = int(sys.argv[sys.argv.index("--year") + 1])
CONVERGENCE = 0.05

# ---------------------------------------------------------------------------
# Parsing du bulletin réel
# ---------------------------------------------------------------------------

_ENTREE_RE = re.compile(r"Entr[ée]\(e\)\s*le\s*:\s*(\d{2})/(\d{2})/(\d{4})")
_ANCIEN_RE = re.compile(r"Anciennet[ée]\s*:\s*(\d{2})/(\d{2})/(\d{4})")
_PAS_RE = re.compile(r"Imp[ôo]t sur le revenu pr[ée]lev[ée] [àa] la source\s+[\d.]+\s+([\d]+\.\d{2})")
# HS structurelles mensuelles (contrat 37,5 h → ~10,83 h/mois à 25 %). Leur
# présence signale que le salaire stocké est la base 151,67 h SANS les HS
# structurelles (payées en sus), donc salaire_hors_hs_structurelles = True.
_HS_STRUCT_RE = re.compile(r"H\. supp majorées à 25 %\s+(10\.8\d)\s")
# Toutes les quantités d'HS 25 % (structurelles ET conjoncturelles) — le tri
# structurel/conjoncturel se fait ensuite contre la durée hebdo du contrat.
_HS25_ALL_RE = re.compile(r"H\. supp majorées à 25 %\s+([\d]+\.\d{2})\s")
# HS CONJONCTURELLES (en sus des structurelles) : lignes « Heures supplémentaires
# 25 » / « Heures supplémentaires 50 » (préfixe différent de « H. supp majorées »).
# Le moteur les consomme via _is_heures_sup_conjoncturelle_input (payroll_quantity).
_HS_CONJ25_RE = re.compile(r"Heures suppl[ée]mentaires 25\s+(\d+\.\d{2})")
_HS_CONJ50_RE = re.compile(r"Heures suppl[ée]mentaires 50\s+(\d+\.\d{2})")
# Ligne « SALAIRE DE BASE » à 151,67 h → le salaire stocké est la base légale
# (HS structurelles payées en sus). Condition robuste pour hors_hs_structurelles.
_BASE_151_RE = re.compile(r"SALAIRE DE BASE\s+151\.67\s")

# Primes taxées (soumises cotisations + impôt). Exclues :
#  - BANC (ancienneté) : calculée par le moteur via seniority_reference_date.
#  - BQCP (arbitrage congés payés) : l'indemnité CP est reconstruite par le
#    moteur depuis les jours CP du calendrier → l'ajouter en prime double-compte.
_PRIME_TAXED_RE = re.compile(
    r"^\s*(BAA|BPAN|BSIC|BPA)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'.() ]*?)\s+"
    r"([\d.]+\.\d{2})(?:\s+([\d.]+\.\d{4}))?\s+([\d.]+\.\d{2})(?=\s{2,}|\s*$)",
    re.MULTILINE,
)
# Primes non soumises (frais pro : paniers jours, indemnités forfaitaires dép.)
_PRIME_NONTAXED_RE = re.compile(
    r"^\s*(SPAN|SND\w?)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'.() ]*?)\s+"
    r"([\d.]+\.\d{2})(?:\s+([\d.]+\.\d{4}))?\s+([\d.]+\.\d{2})(?=\s{2,}|\s*$)",
    re.MULTILINE,
)
_PARTICIPATION_RE = re.compile(
    r"^\s*Participation(?:\s*2025)?\s+([\d]+\.\d{2})\s+([\d]+\.\d{2})(?=\s{2,}|\s*$)",
    re.MULTILINE,
)
_ACOMPTE_RE = re.compile(
    r"Avance participation\s*(?:\d{4})?\s+(-[\d]+\.\d{2})", re.IGNORECASE
)
# Acompte sur salaire versé en cours de mois (« Acompte 05/2026  300.00 ») :
# retenue nette pure (ne touche ni le brut, ni le MNS, ni le net imposable).
_ACOMPTE_SALAIRE_RE = re.compile(r"Acompte\s+\d{2}/\d{4}\s+([\d]+\.\d{2})", re.IGNORECASE)
_PRET_RE = re.compile(
    r"^\s*(?:SAV\w|SAW\w|SBUS)\s+(Contrat de pr[êe]t[^\n]*?)\s+-([\d]+\.\d{2})\s+-([\d]+\.\d{2})(?=\s{2,}|\s*$)",
    re.MULTILINE,
)
_CANTINE_RE = re.compile(
    r"^\s*SCAN\s+Cantine\s+-[\d.]+\s+[\d.]+\s+-([\d]+\.\d{2})(?=\s{2,}|\s*$)", re.MULTILINE
)
# Saisie-arrêt sur salaire (retenue nette). Selon le layout Cegid, le montant
# apparaît soit négatif (« Saisie trésorie Chambéry  -246.02 … », cf. OVIE),
# soit positif en colonne montant salarial (« Saisie Crédit Logement  500.00
# 500.00 », cf. GOISSAUD). On capture le PREMIER nombre de la ligne quel que soit
# son signe (le libellé « Saisie … » ne contient jamais de chiffre), en ignorant
# les colonnes parasites de droite (plafond Sécu 4005.00). Toujours traité comme
# une retenue (montant négatif).
# IGNORECASE : le libellé Cegid apparaît parfois en minuscule (« saisie Trésorie
# du Chambéry 255.79 », OSMANI2 janvier) → retenue nette sur salaire à capter.
_SAISIE_RE = re.compile(r"^\s*Saisie\b[^\n]*?\s+(-?[\d]+\.\d{2})", re.MULTILINE | re.IGNORECASE)
_VIREMENT_RE = re.compile(r"^\s*Virement salaire[^\n]*?\s+([\d]+\.\d{2})", re.MULTILINE)
_MUTUELLE_RE = re.compile(
    r"^\s*EMU\d\s+.+?\s+\d+\.\d{2}\s+"    # base (4005.00)
    r"(?:(\d+\.\d{4})\s+)?"               # taux optionnel (4 décimales)
    r"(\d+\.\d{2})"                       # salarial (ou montant unique)
    r"(?:\s+(\d+\.\d{2}))?",              # patronal optionnel
    re.MULTILINE,
)
# Mutuelle « famille » (Salarié+conjoint+enfants) : la part patronale reste
# soumise à CSG (MNS) mais N'EST PAS réintégrée au net imposable par Cegid
# (cf. MOUSSAFIR/MARZOUG/SPIGA MBC mai 2026). → part_patronale_reintegree_impot=False.
_MUTUELLE_FAMILLE_RE = re.compile(
    r"EMU\d[^\n]*?(?:conjoint|\+\s*enf|famille)", re.IGNORECASE
)
_PREVOYANCE_NONCADRE_RE = re.compile(r"EPR3\s+GAN PREVOYANCE NON CADRE", re.IGNORECASE)
_CP_RANGE_RE = re.compile(
    r"Cong[ée]s pay[ée]s\s*:\s*(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})", re.IGNORECASE
)
_CP_DAY_RE = re.compile(r"Cong[ée]s pay[ée]s\s*:\s*(\d{2})(\d{2})(\d{2})(?!-)", re.IGNORECASE)
_JTC_RE = re.compile(r"JTC\s+Pris\s*=\s*\d+\s*j\s+le\s+([\d ]+(?:et\s+[\d ]+)*)", re.IGNORECASE)
# Absences réelles NON PAYÉES (déduites du brut) : injustifiées, autorisées non
# payées, congés sans solde. Le pointage étant vidé (source = bulletin), on
# réinjecte ces absences comme jours planifiés absence_non_remuneree.
# Journées PLEINES (heures/jour >= 6,5 h) ET fractionnaires (< 6,5 h, ex.
# OZEN mai 2026 MBC : 1,40 h le 13/05, 4,67 h le 22/05) sont toutes deux
# capturées — le moteur (`_heures_evenement_absence` dans calcul_brut.py)
# accepte nativement un nombre d'heures arbitraire, ce n'était qu'une
# limitation du parseur du réconciliateur, pas du moteur.
_ABS_LABEL = (
    r"(?:Abs injustifi\w*|Abs injusti|Abs aut nonpay\w*|Cong[ée]s? s\.so\w*"
    # Événements familiaux déduits du brut : « Abs. Evt familli … » (naissance,
    # événement familial), « Abs. Enfant malade … » — retenus comme une absence
    # non payée (le maintien/IJSS de l'arrêt paternité les couvre à part).
    r"|Evt famil\w*|Enfant malade)"
)
_ABS_RANGE_RE = re.compile(
    r"Abs\.\s+" + _ABS_LABEL + r"\s+(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})\s+(\d+\.\d{2})",
    re.IGNORECASE,
)
_ABS_DAY_RE = re.compile(
    r"Abs\.\s+" + _ABS_LABEL + r"\s+(\d{2})(\d{2})(\d{2})(?!-)\s+(\d+\.\d{2})",
    re.IGNORECASE,
)

# Arrêts de travail (déduits du brut, avec « Maintien de salaire » employeur
# éventuel). Libellés Cegid : « Absence maladie DDMMYY-DDMMYY », « Absence A.T.
# … » (accident du travail), « Abs. paternité … » / « Absence paternité »,
# « Absence maternité ». La plage porte base (heures), taux, puis montant retenu.
_ARRET_LABEL = (
    r"(Absence maladie|Absence\s+A\.?\s?T\.?|(?:Abs\.|Absence)\s+patern\w*"
    r"|(?:Abs\.|Absence)\s+matern\w*)"
)
_ARRET_RANGE_RE = re.compile(
    _ARRET_LABEL
    + r"\s+(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})\s+[\d.]+\s+[\d.]+\s+(\d+\.\d{2})",
    re.IGNORECASE,
)
# « Maintien de salaire AMOUNT » du mois courant. On EXCLUT « Rappel Maintien de
# salaire … de MM/AA à MM/AA » = rappel d'un maintien d'un mois ANTÉRIEUR
# (cross-mois), non modélisable sans le bulletin M-1 → drapeau KNOWN_GAP.
_MAINTIEN_AMOUNT_RE = re.compile(r"^\s*Maintien de salaire\s+(\d+\.\d{2})", re.MULTILINE)
_RAPPEL_MAINTIEN_RE = re.compile(r"Rappel Maintien de salaire\s+(\d+\.\d{2})", re.IGNORECASE)


def _arret_type_from_label(label: str) -> str:
    """Mappe le libellé Cegid vers l'`arret_type` attendu par le moteur maintien."""
    low = label.lower()
    if "patern" in low:
        return "paternite"
    if "matern" in low:
        return "maternite"
    if re.search(r"a\.?\s?t", low) and "maladie" not in low:
        return "accident_travail"
    return "maladie_simple"


def is_frais_pro_non_soumis_label(name: str) -> bool:
    """True si ce libellé de prime est un frais pro non soumis (→ saisie à poser en
    `is_socially_taxed=False`, sinon le montant est réintégré au brut).

    Délègue au moteur (`_is_frais_pro_non_soumis_input`) au lieu de redupliquer une
    liste de libellés : la liste locale avait dérivé de celle du moteur (« Rbst note
    de frais » reconnu côté moteur mais absent ici → saisie créée taxée → +48,19 €
    de brut sur BLONDEAU janvier). Le moteur exige déjà `amount > 0` et
    `is_socially_taxed=False` pour router : on ne teste ici que la sémantique du
    libellé, d'où la ligne synthétique.
    """
    if "soumises" in (name or "").lower():
        return False
    return _is_frais_pro_non_soumis_input(
        {"name": name, "amount": 1.0, "is_socially_taxed": False}
    )
# Libellés à neutraliser : le moteur intercepte tout libellé contenant
# « congés »/« arbitrage » via son propre mécanisme CP → utiliser un nom neutre.
NEUTRAL_NAME = "Ajustement paie divers"


@dataclass
class Expected:
    """Éléments attendus extraits du bulletin réel."""
    primes_taxed: list = field(default_factory=list)       # (name, amount, qty)
    primes_nontaxed: list = field(default_factory=list)    # (name, amount, qty)
    participation: float | None = None
    acompte: float | None = None
    acompte_salaire: float | None = None     # avance sur salaire (retenue nette)
    prets: list = field(default_factory=list)              # (name, amount<0)
    cantine: float | None = None                           # <0
    saisies: list = field(default_factory=list)            # (name, amount<0)
    mutuelle: tuple | None = None          # (salarial, patronal)
    mutuelle_famille: bool = False         # patronal non réintégré au net imposable
    prevoyance_noncadre: bool = False
    seniority_date: str | None = None                      # YYYY-MM-DD si != entrée
    pas_taux: float | None = None
    hors_hs_structurelles: bool = False                    # base 151,67 h + HS en sus
    base_151_67: bool = False                              # ligne SALAIRE DE BASE à 151,67 h
    hs_25_quantities: list = field(default_factory=list)   # toutes les quantités HS 25 %
    hs_conj_25: float = 0.0                                # HS conjoncturelles 25 % (heures)
    hs_conj_50: float = 0.0                                # HS conjoncturelles 50 % (heures)
    cp_days: list = field(default_factory=list)            # jours (int)
    jtc_days: list = field(default_factory=list)           # jours (int)
    absence_days: list = field(default_factory=list)       # jours pleins non payés (int)
    absence_fractionnaire: list = field(default_factory=list)  # (jour, heures<6.5) non payé
    # --- Arrêt de travail (maladie / AT / paternité / maternité) ---
    arret_type: str | None = None          # arret_type moteur (maladie_simple, ...)
    arret_days: list = field(default_factory=list)         # jours ouvrés de l'arrêt (int)
    arret_amount: float = 0.0              # retenue « Absence maladie/… » (100 % absence)
    maintien_amount: float | None = None   # « Maintien de salaire » du mois (None = aucun)
    arret_cross_month: bool = False        # présence d'un « Rappel Maintien » (cross-mois)
    ijss_override: float | None = None     # IJSS back-calc = arret_amount − maintien_amount


_COL_NUM = re.compile(r"\d[\d ]*\.\d{2}")
_COL_HDR = re.compile(r"Rubriques.*Montant salarial.*Mt patronal")


def _montant_colonne(text: str, libelle: str) -> float | None:
    """Montant d'une ligne dont la valeur est dans la colonne « Montant salarial »
    du PDF (pas en fin de ligne). None si en-tête absent ou nombre ambigu."""
    lines = (text or "").split("\n")
    zone = None
    for ln in lines:
        if _COL_HDR.search(ln):
            zone = (ln.index("Montant salarial"), ln.index("Mt patronal"))
            break
    if zone is None:
        return None
    lo, hi = zone
    for ln in lines:
        if libelle in ln:
            cands = [m for m in _COL_NUM.finditer(ln) if lo < m.end() <= hi]
            if len(cands) == 1:
                return round(float(cands[0].group(0).replace(" ", "")), 2)
    return None


def _neutralize(name: str) -> str:
    low = name.lower()
    if "cong" in low or "arbitrage" in low:
        return NEUTRAL_NAME
    return name


def parse_reference(text: str) -> Expected:
    exp = Expected()

    for code, label, base_amt, taux, montant in _PRIME_TAXED_RE.findall(text):
        name = _neutralize(label.strip())
        qty = float(base_amt) if taux else None
        exp.primes_taxed.append((name, float(montant), qty))

    # BSEM « Prime semestrielle » (juin) : prime taxée dont le montant est dans la
    # colonne « Montant salarial » (pas en fin de ligne, comme la base forfait) →
    # extraction par position de colonne. Vérifié = delta brut (GAUDEY 1179,96).
    _bsem = _montant_colonne(text, "BSEM Prime semestrielle")
    if _bsem:
        exp.primes_taxed.append(("Prime semestrielle", _bsem, None))

    for code, label, base_amt, taux, montant in _PRIME_NONTAXED_RE.findall(text):
        exp.primes_nontaxed.append((label.strip(), float(montant), float(base_amt) if taux else None))

    part = _PARTICIPATION_RE.findall(text)
    if part:
        exp.participation = float(part[0][0])
    am = _ACOMPTE_RE.search(text)
    if am:
        exp.acompte = float(am.group(1))
    asm = _ACOMPTE_SALAIRE_RE.search(text)
    if asm:
        exp.acompte_salaire = float(asm.group(1))

    for label, m_s, m_p in _PRET_RE.findall(text):
        exp.prets.append((label.strip(), -float(m_s)))
    cm = _CANTINE_RE.search(text)
    if cm:
        exp.cantine = -float(cm.group(1))
    for amt in _SAISIE_RE.findall(text):
        exp.saisies.append(("Saisie trésorerie", -abs(float(amt))))
    for amt in _VIREMENT_RE.findall(text):
        exp.saisies.append(("Virement salaire (régul.)", -float(amt)))

    mm = _MUTUELLE_RE.findall(text)
    if mm:
        taux, a1, a2 = mm[0]
        if taux:  # taux présent → a1=salarial, a2=patronal
            exp.mutuelle = (float(a1), float(a2) if a2 else float(a1))
        else:      # montant unique = « Mutuelle Isolé » : 100 % employeur.
            # La colonne « Mt patronal » porte le montant, la colonne salariale
            # est vide → salarial = 0 (confirmé empiriquement : LIKAG converge
            # à 0,01 € avec 0/46,86 vs 46,86 d'écart avec 46,86/46,86).
            exp.mutuelle = (0.0, float(a1))
        exp.mutuelle_famille = bool(_MUTUELLE_FAMILLE_RE.search(text))
    if _PREVOYANCE_NONCADRE_RE.search(text):
        exp.prevoyance_noncadre = True

    em, an = _ENTREE_RE.search(text), _ANCIEN_RE.search(text)
    if em and an and em.groups() != an.groups():
        d, mo, y = an.groups()
        exp.seniority_date = f"{y}-{mo}-{d}"

    pm = _PAS_RE.search(text)
    if pm:
        exp.pas_taux = float(pm.group(1))

    if _HS_STRUCT_RE.search(text):
        exp.hors_hs_structurelles = True
    exp.base_151_67 = bool(_BASE_151_RE.search(text))
    exp.hs_25_quantities = [float(q) for q in _HS25_ALL_RE.findall(text)]
    exp.hs_conj_25 = sum(float(q) for q in _HS_CONJ25_RE.findall(text))
    exp.hs_conj_50 = sum(float(q) for q in _HS_CONJ50_RE.findall(text))

    # Congés payés : plages puis jours isolés.
    cp = set()
    ranges_text = text
    for d1, m1, _y, d2, m2, _y2 in _CP_RANGE_RE.findall(text):
        if int(m1) == MONTH:
            cp.update(range(int(d1), int(d2) + 1))
        elif int(m2) == MONTH:
            cp.update(range(1, int(d2) + 1))
    ranges_text = _CP_RANGE_RE.sub("", ranges_text)
    for d, mo, _y in _CP_DAY_RE.findall(ranges_text):
        if int(mo) == MONTH:
            cp.add(int(d))
    exp.cp_days = sorted(cp)

    # JTC : « Pris =2j le 15 et 25-05 » → jours 15, 25.
    jtc = set()
    for grp in _JTC_RE.findall(text):
        for tok in re.split(r"\s+et\s+|\s+", grp.strip()):
            tok = tok.strip().rstrip("-")
            tok = re.sub(r"-\d{2}$", "", tok)  # « 25-05 » → « 25 »
            if tok.isdigit() and 1 <= int(tok) <= 31:
                jtc.add(int(tok))
    exp.jtc_days = sorted(jtc)

    # Absences réelles non payées : journées pleines (>= 6,5 h/j) posées comme
    # jour entier ; journées ISOLÉES fractionnaires (< 6,5 h, un seul jour
    # daté donc heures non ambiguës) posées avec leur montant d'heures exact.
    # Les PLAGES (ranges) fractionnaires restent un résiduel documenté : la
    # répartition des heures entre plusieurs jours d'une plage n'est pas
    # déductible du bulletin sans ambiguïté (ex. combien d'heures pour quel
    # jour précis dans une plage de 3 jours à 21 h ?).
    abs_days: set = set()
    abs_fractional: dict[int, float] = {}
    abs_text = text
    for d1, m1, y1, d2, m2, y2, heures in _ABS_RANGE_RE.findall(text):
        # Les heures d'une plage couvrent les jours OUVRÉS, pas les jours
        # calendaires : « Abs. Congés s.so 120126-310126  105.00 » = 105 h sur les
        # 14 jours ouvrés du 12 au 31/01 = 7,5 h/j (journée pleine), et NON
        # 105/20 = 5,25 h/j comme le donnait le repli calendaire — ce qui faisait
        # skipper à tort la plage comme « fractionnaire » (DAWRAN jan : 1262 € de
        # congés sans solde jamais déduits).
        try:
            start = datetime.date(2000 + int(y1), int(m1), int(d1))
            end = datetime.date(2000 + int(y2), int(m2), int(d2))
        except ValueError:
            continue
        if end < start:
            continue
        span = [start + datetime.timedelta(days=i) for i in range((end - start).days + 1)]
        ouvres = [d for d in span if d.weekday() < 5]
        if not ouvres:
            continue
        per_day = float(heures) / len(ouvres)
        if per_day < 6.5:
            continue  # vraie plage fractionnaire → résiduel documenté (répartition ambiguë)
        abs_days.update(d.day for d in ouvres if d.month == MONTH and d.year == YEAR)
    abs_text = _ABS_RANGE_RE.sub("", abs_text)
    for d, mo, _y, heures in _ABS_DAY_RE.findall(abs_text):
        if int(mo) != MONTH:
            continue
        h = float(heures)
        if h >= 6.5:
            abs_days.add(int(d))
        elif h > 0:
            abs_fractional[int(d)] = h
    # Arrêt de travail (maladie / AT / paternité / maternité) : jours ouvrés de
    # la ou des plage(s) tombant dans le mois courant + montant retenu (pour
    # back-calc de l'IJSS subrogée = absence 100 % − maintien versé).
    arret_days: set = set()
    arret_types: list = []
    arret_amount = 0.0
    premier_du_mois = datetime.date(YEAR, MONTH, 1)
    dernier_du_mois = datetime.date(
        YEAR, MONTH, calendar.monthrange(YEAR, MONTH)[1]
    )
    for label, d1, m1, y1, d2, m2, y2, montant in _ARRET_RANGE_RE.findall(text):
        arret_types.append(_arret_type_from_label(label))
        # Le montant compte toujours : une plage d'un mois antérieur reportée sur
        # ce bulletin (ex. LABBE « Absence maladie 300126-310126 » sur février) y
        # est bien retenue, et son maintien l'est aussi — les deux se compensent
        # dans le back-calc `IJSS = arret_amount − maintien_amount`.
        arret_amount += float(montant)
        try:
            debut = datetime.date(2000 + int(y1), int(m1), int(d1))
            fin = datetime.date(2000 + int(y2), int(m2), int(d2))
        except ValueError:
            continue
        # Seuls les jours réellement DANS le mois courant deviennent des jours
        # d'arrêt. L'ancienne heuristique (`start=1 si m1≠MONTH`, `end=31 si
        # m2≠MONTH`) transformait une plage entièrement extérieure au mois en
        # « tout le mois » : LABBE février voyait ses 20 jours ouvrés marqués en
        # arrêt à cause de la seule plage de janvier.
        lo, hi = max(debut, premier_du_mois), min(fin, dernier_du_mois)
        if lo > hi:
            continue
        for d in range(lo.day, hi.day + 1):
            if datetime.date(YEAR, MONTH, d).weekday() < 5:
                arret_days.add(d)
    # Un jour d'arrêt n'est ni CP/JTC ni absence non payée « classique ».
    arret_days -= set(exp.cp_days) | set(exp.jtc_days)
    abs_days -= arret_days
    exp.arret_days = sorted(arret_days)
    if arret_types:
        # Un seul type par bulletin en pratique ; priorité au 1er non-maladie
        # (paternité/maternité/AT changent le régime légal), sinon maladie.
        non_maladie = [t for t in arret_types if t != "maladie_simple"]
        exp.arret_type = non_maladie[0] if non_maladie else "maladie_simple"
    exp.arret_amount = round(arret_amount, 2)
    maintiens = [float(x) for x in _MAINTIEN_AMOUNT_RE.findall(text)]
    exp.maintien_amount = round(sum(maintiens), 2) if maintiens else None
    exp.arret_cross_month = bool(_RAPPEL_MAINTIEN_RE.search(text))
    # IJSS subrogée back-calculée (SERE/OZEN MBC) : versée = absence 100 % − IJSS,
    # or maintien_cible moteur = absence 100 % (jours ouvrés × taux × 7 h) →
    # IJSS = arret_amount − maintien_amount. Requiert un maintien du mois courant
    # ET l'absence, et l'absence des rappels cross-mois (sinon montants mélangés).
    if (
        exp.maintien_amount is not None
        and exp.arret_amount > 0
        and not exp.arret_cross_month
        and exp.arret_amount - exp.maintien_amount >= 0
    ):
        exp.ijss_override = round(exp.arret_amount - exp.maintien_amount, 2)

    # Un jour déjà CP/JTC/arrêt n'est pas une absence non payée.
    exp.absence_days = sorted(abs_days - set(exp.cp_days) - set(exp.jtc_days))
    exp.absence_fractionnaire = sorted(
        (d, h)
        for d, h in abs_fractional.items()
        if d not in exp.cp_days
        and d not in exp.jtc_days
        and d not in abs_days
        and d not in arret_days
    )

    return exp


# ---------------------------------------------------------------------------
# Snapshot / restore de l'état mutable
# ---------------------------------------------------------------------------

_INPUT_COLS = ("name", "description", "amount", "is_socially_taxed", "is_taxable",
               "payroll_quantity", "catalog_prime_id", "export_code",
               "bonus_type_id", "participation_campaign_id", "participation_bulletin_id")


@dataclass
class Snapshot:
    monthly_inputs: list
    specificites_paie: dict
    seniority_reference_date: str | None
    planned_calendar: dict | None
    actual_hours: dict | None
    schedule_id: str | None


def take_snapshot(admin, employee_id, company_id) -> Snapshot:
    inputs = (admin.table("monthly_inputs").select("*")
              .match({"employee_id": employee_id, "year": YEAR, "month": MONTH})
              .execute().data) or []
    emp = (admin.table("employees")
           .select("specificites_paie,seniority_reference_date")
           .eq("id", employee_id).single().execute().data)
    sched = (admin.table("employee_schedules").select("id,planned_calendar,actual_hours")
             .match({"employee_id": employee_id, "year": YEAR, "month": MONTH})
             .maybe_single().execute())
    sched_data = sched.data if sched else None
    return Snapshot(
        monthly_inputs=copy.deepcopy(inputs),
        specificites_paie=copy.deepcopy(emp.get("specificites_paie") or {}),
        seniority_reference_date=emp.get("seniority_reference_date"),
        planned_calendar=copy.deepcopy((sched_data or {}).get("planned_calendar")),
        actual_hours=copy.deepcopy((sched_data or {}).get("actual_hours")),
        schedule_id=(sched_data or {}).get("id"),
    )


def restore_snapshot(admin, employee_id, company_id, snap: Snapshot):
    # monthly_inputs : purge + réinsertion à l'identique
    admin.table("monthly_inputs").delete().match(
        {"employee_id": employee_id, "year": YEAR, "month": MONTH}
    ).execute()
    for row in snap.monthly_inputs:
        payload = {k: row.get(k) for k in _INPUT_COLS}
        payload.update({"employee_id": employee_id, "company_id": company_id,
                        "year": YEAR, "month": MONTH})
        admin.table("monthly_inputs").insert(payload).execute()
    admin.table("employees").update({
        "specificites_paie": snap.specificites_paie,
        "seniority_reference_date": snap.seniority_reference_date,
    }).eq("id", employee_id).execute()
    if snap.schedule_id:
        payload = {}
        if snap.planned_calendar is not None:
            payload["planned_calendar"] = snap.planned_calendar
        if snap.actual_hours is not None:
            payload["actual_hours"] = snap.actual_hours
        if payload:
            admin.table("employee_schedules").update(payload).eq(
                "id", snap.schedule_id
            ).execute()


# ---------------------------------------------------------------------------
# Application des corrections
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    return "".join(c for c in (s or "").upper() if c.isalnum())


def _resolve_mutuelle_type(admin, company_id, sal: float, pat: float) -> str:
    """Retourne l'id d'une entreprise_mutuelle_type avec ces montants
    salarial/patronal exacts, en la créant si absente. Évite les entrées
    buggées à patronal=0 (bug d'import DSN récurrent)."""
    rows = (admin.table("company_mutuelle_types")
            .select("id,montant_salarial,montant_patronal")
            .eq("company_id", company_id).eq("is_active", True).execute().data) or []
    for r in rows:
        rs = r.get("montant_salarial")
        rp = r.get("montant_patronal")
        if rs is None or rp is None:
            continue
        if abs(rs - sal) < 0.005 and abs(rp - pat) < 0.005:
            return r["id"]
    created = (admin.table("company_mutuelle_types").insert({
        "company_id": company_id,
        "libelle": f"Mutuelle {sal:.2f}€ / {pat:.2f}€",
        "montant_salarial": sal, "montant_patronal": pat,
        "part_patronale_soumise_a_csg": True, "is_active": True,
        "pack_couverture": "autre", "statut_categoriel": "non_cadre",
        "source": "manual",
    }).execute().data)
    return created[0]["id"]


def apply_expected(admin, employee_id, company_id, exp: Expected) -> list[str]:
    actions: list[str] = []

    # --- Reconstruction complète des monthly_inputs depuis le bulletin ---
    # (purge + rebuild : corrige aussi les données parasites/erronées ; le
    # revert auto protège si le parseur a raté un élément.)
    admin.table("monthly_inputs").delete().match(
        {"employee_id": employee_id, "year": YEAR, "month": MONTH}
    ).execute()

    rebuilt: list[dict] = []

    def add(name, amount, *, taxed, taxable, qty=None):
        row = {"employee_id": employee_id, "company_id": company_id,
               "year": YEAR, "month": MONTH, "name": name, "amount": amount,
               "is_socially_taxed": taxed, "is_taxable": taxable}
        if qty is not None:
            row["payroll_quantity"] = qty
        rebuilt.append(row)

    for name, amount, qty in exp.primes_taxed:
        add(name, amount, taxed=True, taxable=True, qty=qty)
    for name, amount, qty in exp.primes_nontaxed:
        non_taxed = is_frais_pro_non_soumis_label(name)
        add(name, amount, taxed=not non_taxed, taxable=not non_taxed, qty=qty)
    if exp.participation is not None:
        add("Participation 2025 — numéraire", exp.participation, taxed=False, taxable=True)
    if exp.acompte is not None:
        add("Avance participation 2025 (déjà versée)", exp.acompte, taxed=False, taxable=False)
    if exp.acompte_salaire is not None:
        # Retenue nette pure → routée net-only par le générateur (libellé « Acompte »).
        add("Acompte 05/2026", -exp.acompte_salaire, taxed=False, taxable=False)
    if exp.cantine is not None:
        add("Cantine", exp.cantine, taxed=True, taxable=True)
    for name, amount in exp.prets:
        add(name, amount, taxed=False, taxable=False)
    for name, amount in exp.saisies:
        add(name, amount, taxed=False, taxable=False)

    for row in rebuilt:
        admin.table("monthly_inputs").insert(row).execute()
    actions.append(f"monthly_inputs reconstruits ({len(rebuilt)})")

    # specificites_paie : mutuelle + prévoyance non-cadre 0,5%/0,5% + taux PAS
    emp = (admin.table("employees").select("specificites_paie,duree_hebdomadaire")
           .eq("id", employee_id).single().execute().data)
    sp = emp.get("specificites_paie") or {}
    changed = False

    # hors_hs_structurelles (généralisé) : la ligne SALAIRE DE BASE est à 151,67 h
    # et le bulletin porte une ligne HS 25 % dont la quantité = les HS structurelles
    # mensualisées du contrat = round((durée_hebdo - 35) * 52 / 12, 2). Robuste à
    # tout volume d'HS (10,83 h pour 37,5 h ; 7,24 h pour 36,67 h ; etc.).
    if exp.base_151_67 and not exp.hors_hs_structurelles:
        duree = float(emp.get("duree_hebdomadaire") or 35)
        if duree > 35:
            struct_qty = round((duree - 35) * 52 / 12, 2)
            if any(abs(q - struct_qty) < 0.05 for q in exp.hs_25_quantities):
                exp.hors_hs_structurelles = True

    if exp.mutuelle is not None:
        sal, pat = exp.mutuelle
        mut_id = _resolve_mutuelle_type(admin, company_id, sal, pat)
        mut = sp.setdefault("mutuelle", {})
        if not mut.get("adhesion") or mut.get("mutuelle_type_ids") != [mut_id]:
            mut["adhesion"] = True
            mut["mutuelle_type_ids"] = [mut_id]
            mut["lignes_specifiques"] = []
            changed = True
            actions.append(f"mutuelle {sal}/{pat}")
        # Mutuelle famille : part patronale non réintégrée au net imposable.
        want_reint = not exp.mutuelle_famille
        if mut.get("part_patronale_reintegree_impot", True) != want_reint:
            mut["part_patronale_reintegree_impot"] = want_reint
            changed = True
            actions.append(f"mutuelle réintégration IR={want_reint}")
    if exp.prevoyance_noncadre:
        prev = sp.setdefault("prevoyance", {})
        lignes = prev.get("lignes_specifiques") or []
        if not prev.get("adhesion") or not lignes or \
           lignes[0].get("patronal") != 0.005 or lignes[0].get("salarial") != 0.005:
            prev["adhesion"] = True
            prev["lignes_specifiques"] = [{
                "id": "prevoyance_dsn", "base": "brut_plafonne",
                "libelle": "Prévoyance (import DSN)",
                "patronal": 0.005, "salarial": 0.005, "forfait_social": 0.08,
            }]
            changed = True
            actions.append("prévoyance non-cadre 0.5%/0.5%")
    if exp.pas_taux is not None:
        pas = sp.setdefault("prelevement_a_la_source", {})
        if abs((pas.get("taux") or -1) - exp.pas_taux) > 0.001:
            pas["taux"] = exp.pas_taux
            changed = True
            actions.append(f"taux PAS -> {exp.pas_taux}")
    if exp.hors_hs_structurelles and not sp.get("salaire_hors_hs_structurelles"):
        sp["salaire_hors_hs_structurelles"] = True
        changed = True
        actions.append("salaire hors HS structurelles")
    if changed:
        admin.table("employees").update({"specificites_paie": sp}).eq("id", employee_id).execute()

    # seniority_reference_date
    if exp.seniority_date:
        cur = admin.table("employees").select("seniority_reference_date").eq("id", employee_id).single().execute().data
        if (cur.get("seniority_reference_date") or "")[:10] != exp.seniority_date:
            admin.table("employees").update({"seniority_reference_date": exp.seniority_date}).eq("id", employee_id).execute()
            actions.append(f"ancienneté -> {exp.seniority_date}")

    # Calendrier : CP + JTC (payés) + absences non payées (déduites)
    if exp.cp_days or exp.jtc_days or exp.absence_days or exp.absence_fractionnaire:
        actions += _apply_calendar(admin, employee_id, exp)

    # Pointage (actual_hours) corrompu : les heures réelles (ex. 7,4 h au lieu de
    # 7,5 h prévues, ou jours manquants) génèrent des « Absence injustifiée »
    # fantômes qui sur-déduisent le brut. Pour le backtest, la source de vérité
    # est le bulletin (calendrier prévu + absences réelles reconstruites), pas le
    # pointage. On vide donc calendrier_reel → mois_sans_pointage → base préservée.
    actions += _clear_actual_hours(admin, employee_id)

    return actions


def _clear_actual_hours(admin, employee_id) -> list[str]:
    sched = (admin.table("employee_schedules").select("id,actual_hours")
             .match({"employee_id": employee_id, "year": YEAR, "month": MONTH})
             .maybe_single().execute())
    if not sched or not sched.data:
        return []
    ah = sched.data.get("actual_hours") or {}
    if not ah.get("calendrier_reel"):
        return []
    ah = copy.deepcopy(ah)
    ah["calendrier_reel"] = []
    admin.table("employee_schedules").update({"actual_hours": ah}).eq(
        "id", sched.data["id"]
    ).execute()
    return ["actual_hours vidé (pointage corrompu)"]


def _apply_calendar(admin, employee_id, exp: Expected) -> list[str]:
    actions: list[str] = []
    sched = (admin.table("employee_schedules").select("id,planned_calendar")
             .match({"employee_id": employee_id, "year": YEAR, "month": MONTH})
             .maybe_single().execute())
    if not sched or not sched.data:
        return actions
    planned = sched.data.get("planned_calendar") or {}
    cal = planned.get("calendrier_prevu", [])
    by_day = {j.get("jour"): j for j in cal}
    changed = False

    def set_day(day, new_type, heures=7.5):
        nonlocal changed
        j = by_day.get(day)
        if j is None:
            cal.append({"jour": day, "type": new_type, "manuel": True, "heures_prevues": heures})
            changed = True
            actions.append(f"cal +{day}->{new_type}")
        elif j.get("type") != new_type:
            j["type"] = new_type
            j["manuel"] = True
            # Absence non rémunérée : déduction sur la référence légale 7 h/jour
            # (comme Cegid) → forcer 7,0 même si le jour prévu portait 7,5 h.
            if new_type == "absence_non_remuneree":
                j["heures_prevues"] = heures
            elif not j.get("heures_prevues"):
                j["heures_prevues"] = heures
            changed = True
            actions.append(f"cal {day}:{new_type}")

    for d in exp.cp_days:
        set_day(d, "conges_payes")
    for d in exp.jtc_days:
        if d not in exp.cp_days:
            set_day(d, "absence_justifiee")  # jour de repos payé, sans retenue
    for d in exp.absence_days:
        if d not in exp.cp_days and d not in exp.jtc_days:
            set_day(d, "absence_non_remuneree", heures=7.0)  # journée pleine déduite (7 h légal)
    for d, h in exp.absence_fractionnaire:
        if d not in exp.cp_days and d not in exp.jtc_days:
            set_day(d, "absence_non_remuneree", heures=h)  # absence fractionnaire, heures exactes

    if changed:
        planned["calendrier_prevu"] = sorted(cal, key=lambda j: j["jour"])
        admin.table("employee_schedules").update({"planned_calendar": planned}).eq("id", sched.data["id"]).execute()
    return actions


# ---------------------------------------------------------------------------
# Boucle auto-vérifiante
# ---------------------------------------------------------------------------

def tier_s(match) -> float:
    _generate_payslip(match, YEAR, MONTH)
    for r in compare_matches([match], YEAR, MONTH, thresholds=default_thresholds(),
                             systemic_deltas={}, correction_attempts={}):
        return r.tier_s_max_delta
    return float("inf")


def reconcile(match, admin) -> dict:
    matricule = match.matricule
    before = tier_s(match)
    if before <= CONVERGENCE:
        return {"matricule": matricule, "before": before, "after": before,
                "status": "déjà convergé", "actions": []}

    snap = take_snapshot(admin, match.employee_id, match.company_id)
    try:
        exp = parse_reference(match.reference.raw_text or "")
        actions = apply_expected(admin, match.employee_id, match.company_id, exp)
        if not actions:
            return {"matricule": matricule, "before": before, "after": before,
                    "status": "rien à faire", "actions": []}
        after = tier_s(match)
    except Exception as exc:
        # Toute erreur (ex. serveur transitoire) en cours d'application ou de
        # régénération : revenir à l'état snapshot avant de propager, pour ne
        # jamais laisser un salarié dans un état partiel non vérifié.
        try:
            restore_snapshot(admin, match.employee_id, match.company_id, snap)
        except Exception:
            pass
        return {"matricule": matricule, "before": before, "after": before,
                "status": f"ERREUR (revert) {exc}", "actions": []}

    if after < before - 0.01:
        return {"matricule": matricule, "before": before, "after": after,
                "status": "amélioré", "actions": actions}
    # revert
    restore_snapshot(admin, match.employee_id, match.company_id, snap)
    reverted = tier_s(match)
    return {"matricule": matricule, "before": before, "after": reverted,
            "status": f"revert (essai={after:.2f})", "actions": actions}


def main():
    admin = get_supabase_admin_client()
    # PDF du mois cible (les mois historiques ne sont pas au chemin par défaut).
    from scripts.backtest.bulletins_source import resolve_bulletin_pdf
    refs = load_reference_bulletins(
        COMPANY, YEAR, MONTH, pdf_path=resolve_bulletin_pdf(COMPANY, YEAR, MONTH)
    )
    cid = resolve_company_id(COMPANY)
    matched = match_employees(cid, refs).matched
    # argv : matricules seuls (on écarte les options et leurs valeurs).
    argv = sys.argv[1:]
    skip: set[int] = set()
    for i, a in enumerate(argv):
        if a in ("--month", "--year"):
            skip.add(i)
            skip.add(i + 1)
    wanted = {a for i, a in enumerate(argv) if i not in skip and not a.startswith("--")}
    if wanted:
        matched = [m for m in matched if m.matricule in wanted]

    results = []
    for m in matched:
        try:
            res = reconcile(m, admin)
        except Exception as exc:  # pragma: no cover
            res = {"matricule": m.matricule, "before": -1, "after": -1,
                   "status": f"ERREUR {exc}", "actions": []}
        results.append(res)
        print(f"[{res['matricule']:14s}] {res['before']:8.2f} -> {res['after']:8.2f}  {res['status']}", flush=True)
        for a in res["actions"]:
            print(f"      · {a}", flush=True)

    print("\n=== RÉSUMÉ ===", flush=True)
    improved = [r for r in results if r["status"] == "amélioré"]
    reverted = [r for r in results if r["status"].startswith("revert")]
    total_gain = sum(r["before"] - r["after"] for r in improved)
    print(f"améliorés : {len(improved)} | revert : {len(reverted)} | gain cumulé : {total_gain:.0f}€", flush=True)


if __name__ == "__main__":
    main()
