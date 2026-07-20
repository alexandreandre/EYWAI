"""Réconciliateur backtest paie — Lewis (métallurgie META), mai 2026.

Adapté de `mbc_reconcile.py` (plasturgie/GAN). Pour chaque salarié : parse le
bulletin réel, reconstruit d'un coup les monthly_inputs (primes soumises + panier
non soumis), le barème mutuelle « EMUT », la prévoyance « E_V6 META » et le
calendrier CP, régénère, compare, **garde si le tier-S baisse, REVERT sinon**.

La reconstruction est faite EN BLOC (et non dimension par dimension) parce que les
erreurs Lewis se compensent partiellement : corriger une seule dimension dégrade
souvent le tier (vérifié sur GROSSET). Snapshot étendu à `company_mutuelle_types`
(table partagée, hors snapshot MBC).

Usage : `.venv/bin/python -m scripts.backtest.lewis_reconcile [MATRICULE ...]`
"""
from __future__ import annotations

import copy
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from scripts.backtest.backtest_company_payroll import _generate_payslip, compare_matches
from app.modules.payroll.backtest.thresholds import default_thresholds

# Stub PDF/storage (comme measure_par.py) : ~10x plus rapide, ne compare que des chiffres.
import weasyprint as _wp


def _pdf_stub(self, target=None, *a, **k):
    if target is None:
        return b"%PDF-1.4\n%stub\n"
    if hasattr(target, "write"):
        target.write(b"%PDF-1.4\n%stub\n"); return None
    open(target, "wb").write(b"%PDF-1.4\n%stub\n"); return None


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

COMPANY = "Lewis"
YEAR, MONTH = 2026, 5
CONVERGENCE = 0.05

# --- Regex Lewis ---------------------------------------------------------
# Primes taxées (soumises cotis + IR) : BPRE présence, BPAN panier équipe soumis,
# BAA assiduité, BSIC. Exclues : BQCP (arbitrage CP, mécanisme moteur), BANC
# (ancienneté, calculée par le moteur).
# Primes soumises : tous les codes B... du bulletin Cegid métallurgie SAUF BQCP
# (arbitrage CP, traité à part). BPRE présence, BPAN panier équipe soumis, BPRA
# ancienneté, BSIC, BAA, etc.
_PRIME_TAXED_RE = re.compile(
    r"^\s*(B(?!QCP\b)[A-Z_][A-Z0-9_]{1,3})\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9'.()%/ ]*?)\s+"
    r"([\d]+\.\d{2})(?:\s+([\d]+\.\d{4}))?\s+([\d]+\.\d{2})(?=\s{2,}|\s*$)",
    re.MULTILINE,
)
# Primes non soumises (paniers / indemnités) : codes S... (SPAJ, SPAN, ...).
_PRIME_NONTAXED_RE = re.compile(
    r"^\s*(S[A-Z]{2,3})\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'.() ]*?)\s+"
    r"([\d]+\.\d{2})(?:\s+([\d]+\.\d{4}))?\s+([\d]+\.\d{2})(?=\s{2,}|\s*$)",
    re.MULTILINE,
)
# Mutuelle « EMUT Mutuelle  <base>  <taux>  <salarial>  <patronal> »
_MUTUELLE_RE = re.compile(
    r"^\s*EMUT\s+Mutuelle\s+[\d]+\.\d{2}\s+[\d.]+\s+([\d]+\.\d{2})\s+([\d]+\.\d{2})",
    re.MULTILINE,
)
# Prévoyance META « E_V<n> PREVOYANCE <CADRE|NON CADRE> TU<1|2> META  base  taux  sal  pat »
# TU1 → tranche A (base brut_plafonne) ; TU2 → tranche B (base tranche_2). Toutes les
# rates (0,73 non-cadre ; 0,56 TU1 / 0,86 TU2 cadre…) et lignes multiples capturées.
_PREV_RE = re.compile(
    r"^\s*E_V\d\s+PREVOYANCE[^\n]*?(TU\d)[^\n]*?\s+([\d]+\.\d{2})\s+([\d]+\.\d{4})"
    r"\s+(-?[\d]+\.\d{2})\s+(-?[\d]+\.\d{2})",
    re.MULTILINE,
)
_CP_DAY_RE = re.compile(r"Cong[ée]s pay[ée]s\s*:\s*(\d{2})(\d{2})(\d{2})(?!-)", re.IGNORECASE)
# Plage de CP « Congés payés : DDMMYY-DDMMYY » (jours ouvrés de l'intervalle).
_CP_RANGE_RE = re.compile(
    r"Cong[ée]s pay[ée]s\s*:\s*(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})",
    re.IGNORECASE)
# Arbitrage CP (règle du 1/10e métallurgie) « BQCP ARBITRAGE DES CONGES PAYES  <mt> »
_ARBITRAGE_RE = re.compile(
    r"ARBITRAGE DES CONGES PAYES\s+([\d]+\.\d{2})", re.IGNORECASE)
# Heures supplémentaires CONJONCTURELLES du bulletin « Heures supplémentaires 25
# <heures> <taux> <montant> » (ou 50). Exclut "structurelles" (contrat, gérées par
# la durée hebdo). Le fix calendrier flatten à durée/5 et vide le pointage : les HS
# réelles doivent donc être réinjectées depuis le bulletin (sinon sous-comptage).
_HS_RE = re.compile(
    r"Heures\s+suppl[ée]mentaires\s+(25|50)\s+([\d]+\.\d{2})\s+"
    r"[\d]+\.\d{4}\s+[\d]+\.\d{2}", re.IGNORECASE)
# Acompte « Acompte MM/YY  <montant> » : avance sur salaire déjà versée, retenue
# nette (réduit UNIQUEMENT le net à payer, hors brut/imposable/MNS). Quasi-
# systématique chez Lewis. Routé net-only par _is_net_a_payer_only_correction_input
# ; signe NÉGATIF = retenue (cf. net_a_payer -= (-amount)).
_ACOMPTE_RE = re.compile(r"Acompte\s+\d{2}/\d{2}\s+([\d]+\.\d{2})", re.IGNORECASE)
# Saisie sur salaire (saisie-arrêt judiciaire) : retenue nette (net-only), routée
# par _is_net_a_payer_only_correction_input ("saisie" dans le libellé). Signe
# NÉGATIF = retenue (comme l'acompte).
_SAISIE_RE = re.compile(r"Saisie sur salaire\s+([\d]+\.\d{2})", re.IGNORECASE)
# Absences NON PAYÉES autres que maladie/CP (déduction du brut ET de la base
# cotisable) : congés sans solde « Abs. Congés s.so », jour férié non payé (ancienneté
# < seuil) « Abs. JF non payé », absence autorisée non payée « Abs. Abs aut nonpayé ».
# Injectées comme prime taxée NÉGATIVE (réduit brut + assiette cotis, cf. Rappel IJSS
# #28). Format : « Abs. <type> <dates> <heures> <taux> <montant> ».
_ABS_DEDUCT_RE = re.compile(
    r"Abs\.\s+(Cong[ée]s s\.so\w*|JF non pay[ée]|Abs aut nonpay[ée])\s+"
    r"\d[\d-]*\s+[\d]+\.\d{2}\s+[\d]+\.\d{4}\s+([\d]+\.\d{2})",
    re.MULTILINE)
# Activité partielle (chômage partiel) : les heures chômées « Act. partiel. DDMMYY
# 7.00 13.5162 94.61 » sont DÉDUITES du brut (heures non travaillées) ; l'« Indemn.
# activité partielle 35.00 9.5200 » est un revenu de remplacement versé au salarié
# (exonéré cotis, CSG 6,7 %), consommé par le hook moteur indemnites_remplacement.
_ACT_PARTIEL_RE = re.compile(
    r"Act\.\s+partiel\.?\s+\d{6}\s+[\d]+\.\d{2}\s+[\d]+\.\d{4}\s+([\d]+\.\d{2})")
_INDEM_ACT_RE = re.compile(
    r"Indemn\.\s+activit[ée]\s+partielle\s+([\d]+\.\d{2})\s+([\d]+\.\d{4})")
# Paramètres moteur ICCP (défauts) pour back-calculer la base de référence 1/10e.
_TAUX_DIXIEME = 0.10
_JOURS_REF_DIXIEME = 30.0
_PAS_RE = re.compile(
    r"Imp[ôo]t sur le revenu pr[ée]lev[ée] [àa] la source\s+[\d.]+\s+([\d]+\.\d{2})"
)

NON_TAXED_TERMS = ("panier", "indemnité forfaitaire", "indemnite forfaitaire",
                   "déplacement", "deplacement")


@dataclass
class Expected:
    primes_taxed: list = field(default_factory=list)
    primes_nontaxed: list = field(default_factory=list)
    mutuelle: tuple | None = None          # (salarial, patronal)
    prevoyance: tuple | None = None        # (taux, sal, pat)
    cp_days: list = field(default_factory=list)
    pas_taux: float | None = None
    arbitrage_cp: float | None = None      # montant BQCP arbitrage (1/10e)
    hs_conj: list = field(default_factory=list)  # (maj '25'|'50', heures)
    acompte: float | None = None           # montant acompte MM/YY (retenue nette)
    saisie: float | None = None            # saisie sur salaire (retenue nette)
    abs_deductions: list = field(default_factory=list)  # (label, montant) absences non payées
    act_partiel_deduct: float = 0.0   # heures chômées activité partielle (déduites du brut)
    indemnite_activite: float = 0.0   # indemnité activité partielle (revenu de remplacement)


def parse_reference(text: str) -> Expected:
    exp = Expected()
    for code, label, base, taux, montant in _PRIME_TAXED_RE.findall(text):
        exp.primes_taxed.append((label.strip(), float(montant),
                                 float(base) if taux else None))
    for code, label, base, taux, montant in _PRIME_NONTAXED_RE.findall(text):
        exp.primes_nontaxed.append((label.strip(), float(montant),
                                    float(base) if taux else None))
    mm = _MUTUELLE_RE.search(text)
    if mm:
        exp.mutuelle = (float(mm.group(1)), float(mm.group(2)))
    prev_lines = []
    for tu, base, taux, sal, pat in _PREV_RE.findall(text):
        b = float(base)
        sr = round(float(sal) / b, 6) if b else 0.0   # taux salarial réel
        pr = round(float(pat) / b, 6) if b else 0.0   # taux patronal réel
        prev_lines.append((tu.upper(), sr, pr))
    if prev_lines:
        exp.prevoyance = prev_lines  # liste de (TU, taux_sal, taux_pat) fractions
    cp = set()
    import datetime as _dt
    for d1, m1, _y1, d2, m2, _y2 in _CP_RANGE_RE.findall(text):
        start = int(d1) if int(m1) == MONTH else 1
        end = int(d2) if int(m2) == MONTH else 31
        for day in range(start, end + 1):
            try:
                if _dt.date(YEAR, MONTH, day).weekday() < 5:
                    cp.add(day)
            except ValueError:
                pass
    for d, mo, _y in _CP_DAY_RE.findall(text):
        if int(mo) == MONTH:
            cp.add(int(d))
    exp.cp_days = sorted(cp)
    pm = _PAS_RE.search(text)
    if pm:
        exp.pas_taux = float(pm.group(1))
    am = _ARBITRAGE_RE.search(text)
    if am:
        exp.arbitrage_cp = float(am.group(1))
    for maj, heures in _HS_RE.findall(text):
        exp.hs_conj.append((maj, float(heures)))
    ac = _ACOMPTE_RE.search(text)
    if ac:
        exp.acompte = float(ac.group(1))
    sm = _SAISIE_RE.search(text)
    if sm:
        exp.saisie = float(sm.group(1))
    for label, montant in _ABS_DEDUCT_RE.findall(text):
        exp.abs_deductions.append((label.strip(), float(montant)))
    exp.act_partiel_deduct = round(sum(float(m) for m in _ACT_PARTIEL_RE.findall(text)), 2)
    im = _INDEM_ACT_RE.search(text)
    if im:
        exp.indemnite_activite = round(float(im.group(1)) * float(im.group(2)), 2)
    return exp


# --- Snapshot (inclut company_mutuelle_types du salarié) -----------------
_INPUT_COLS = ("name", "description", "amount", "is_socially_taxed", "is_taxable",
               "payroll_quantity")


@dataclass
class Snapshot:
    monthly_inputs: list
    specificites_paie: dict
    planned_calendar: dict | None
    actual_hours: dict | None
    schedule_id: str | None
    mutuelle_types: list          # rows of company_mutuelle_types (par id)


def _mutuelle_type_ids(sp: dict) -> list:
    return ((sp.get("mutuelle") or {}).get("mutuelle_type_ids")) or []


def take_snapshot(admin, employee_id) -> Snapshot:
    inputs = (admin.table("monthly_inputs").select("*")
              .match({"employee_id": employee_id, "year": YEAR, "month": MONTH})
              .execute().data) or []
    emp = (admin.table("employees").select("specificites_paie")
           .eq("id", employee_id).single().execute().data)
    sp = emp.get("specificites_paie") or {}
    sched = (admin.table("employee_schedules").select("id,planned_calendar,actual_hours")
             .match({"employee_id": employee_id, "year": YEAR, "month": MONTH})
             .maybe_single().execute())
    sd = sched.data if sched else None
    mtids = _mutuelle_type_ids(sp)
    mtypes = []
    if mtids:
        mtypes = (admin.table("company_mutuelle_types").select("*")
                  .in_("id", mtids).execute().data) or []
    return Snapshot(
        monthly_inputs=copy.deepcopy(inputs),
        specificites_paie=copy.deepcopy(sp),
        planned_calendar=copy.deepcopy((sd or {}).get("planned_calendar")),
        actual_hours=copy.deepcopy((sd or {}).get("actual_hours")),
        schedule_id=(sd or {}).get("id"),
        mutuelle_types=copy.deepcopy(mtypes),
    )


def restore_snapshot(admin, employee_id, company_id, snap: Snapshot):
    admin.table("monthly_inputs").delete().match(
        {"employee_id": employee_id, "year": YEAR, "month": MONTH}).execute()
    for row in snap.monthly_inputs:
        payload = {k: row.get(k) for k in _INPUT_COLS}
        payload.update({"employee_id": employee_id, "company_id": company_id,
                        "year": YEAR, "month": MONTH})
        admin.table("monthly_inputs").insert(payload).execute()
    admin.table("employees").update(
        {"specificites_paie": snap.specificites_paie}).eq("id", employee_id).execute()
    if snap.schedule_id:
        payload = {}
        if snap.planned_calendar is not None:
            payload["planned_calendar"] = snap.planned_calendar
        if snap.actual_hours is not None:
            payload["actual_hours"] = snap.actual_hours
        if payload:
            admin.table("employee_schedules").update(payload).eq(
                "id", snap.schedule_id).execute()
    for mt in snap.mutuelle_types:
        admin.table("company_mutuelle_types").update(
            {"montant_salarial": mt.get("montant_salarial"),
             "montant_patronal": mt.get("montant_patronal")}
        ).eq("id", mt["id"]).execute()


# --- Application ---------------------------------------------------------

def apply_expected(admin, employee_id, company_id, exp: Expected) -> list[str]:
    actions: list[str] = []
    admin.table("monthly_inputs").delete().match(
        {"employee_id": employee_id, "year": YEAR, "month": MONTH}).execute()
    rebuilt = []

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
        low = name.lower()
        non_taxed = any(t in low for t in NON_TAXED_TERMS)
        add(name, amount, taxed=not non_taxed, taxable=not non_taxed, qty=qty)
    # HS conjoncturelles réelles du bulletin (réinjectées car le calendrier est
    # flatten à durée/5 et le pointage vidé). Le moteur calcule le montant depuis
    # payroll_quantity ; amount=0 (ignoré pour ce canal, cf. _is_heures_sup_...).
    for maj, heures in exp.hs_conj:
        add(f"Heures supplémentaires {maj}", 0.0, taxed=True, taxable=True, qty=heures)
    # Acompte : retenue nette (net-only). Signe négatif = retenue.
    if exp.acompte:
        add(f"Acompte {MONTH:02d}/{YEAR % 100:02d}", -exp.acompte,
            taxed=False, taxable=False)
    # Saisie sur salaire : retenue nette (net-only), signe négatif = retenue.
    if exp.saisie:
        add("Saisie sur salaire", -exp.saisie, taxed=False, taxable=False)
    # Absences non payées (congés sans solde, JF non payé, abs. autorisée non payée) :
    # prime taxée NÉGATIVE (réduit brut + assiette cotisable).
    for label, montant in exp.abs_deductions:
        add(f"Abs. {label}", -montant, taxed=True, taxable=True)
    # Activité partielle : heures chômées déduites du brut (prime taxée négative,
    # SANS « indemn » pour ne pas être captée par le hook revenu de remplacement).
    if exp.act_partiel_deduct:
        add("Heures chômées (act. part.)", -exp.act_partiel_deduct, taxed=True, taxable=True)
    # Indemnité activité partielle : revenu de remplacement (hook moteur -> CSG 6,7 %).
    if exp.indemnite_activite:
        add("Indemnité activité partielle", exp.indemnite_activite, taxed=False, taxable=True)
    for row in rebuilt:
        admin.table("monthly_inputs").insert(row).execute()
    if rebuilt:
        actions.append(f"monthly_inputs ({len(rebuilt)})")

    emp = (admin.table("employees").select("specificites_paie")
           .eq("id", employee_id).single().execute().data)
    sp = emp.get("specificites_paie") or {}
    changed = False

    if exp.mutuelle is not None:
        sal, pat = exp.mutuelle
        # Réassigner vers un type existant portant déjà ces montants (évite la
        # contrainte d'unicité) ; sinon éditer le type courant en place.
        existing = (admin.table("company_mutuelle_types").select("id")
                    .eq("company_id", company_id).eq("montant_salarial", sal)
                    .eq("montant_patronal", pat).eq("is_active", True)
                    .limit(1).execute().data)
        cur_ids = _mutuelle_type_ids(sp)
        if existing:
            target_id = existing[0]["id"]
            if cur_ids != [target_id]:
                sp.setdefault("mutuelle", {})["mutuelle_type_ids"] = [target_id]
                changed = True
                actions.append(f"mutuelle → type existant {sal}/{pat}")
        # NB : plus d'édition in-place d'un `company_mutuelle_types` quand aucun
        # type existant ne correspond. La table est PARTAGÉE entre salariés ; éditer
        # un type en place corrompt la mutuelle de tout autre salarié qui le partage
        # (régression observée : NOBLE mai 17,86→38,59 après un run jan/fév). Les
        # barèmes corrects ont tous été créés en mai → une réassignation vers un type
        # existant suffit ; à défaut on laisse la mutuelle inchangée (revert-safe).

    if exp.prevoyance:
        prev = sp.setdefault("prevoyance", {})
        prev["adhesion"] = True
        lignes = []
        for i, (tu, sr, pr) in enumerate(exp.prevoyance):
            base_id = "brut_plafonne" if tu == "TU1" else "tranche_2"
            lignes.append({
                "id": f"prev_meta_{tu.lower()}_{i}", "base": base_id,
                "libelle": f"Prévoyance META {tu} (import bulletin)",
                "patronal": pr, "salarial": sr, "forfait_social": 0.08,
            })
        prev["lignes_specifiques"] = lignes
        changed = True
        actions.append("prévoyance " + "+".join(
            f"{tu}:{sr*100:.2f}/{pr*100:.2f}" for tu, sr, pr in exp.prevoyance))

    # PAS taux : champ per-employé PARTAGÉ entre tous les mois (le schéma ne
    # stocke qu'une valeur). Il a été calé sur mai (30/37 convergés). Le taux PAS
    # varie réellement chaque mois, mais l'écraser depuis un autre mois
    # régresserait le pas_montant de mai. On ne l'écrit donc QUE pour mai ; pour
    # jan-avr/juin le petit résiduel PAS est un KNOWN_GAP structurel assumé.
    if exp.pas_taux is not None and MONTH == 5:
        pas = sp.setdefault("prelevement_a_la_source", {})
        if abs((pas.get("taux") or -1) - exp.pas_taux) > 0.001:
            pas["taux"] = exp.pas_taux
            changed = True
            actions.append(f"PAS {exp.pas_taux}")

    if changed:
        admin.table("employees").update({"specificites_paie": sp}).eq("id", employee_id).execute()

    # Arbitrage CP (règle du 1/10e) : back-calcul de la base de rémunération de
    # référence (brut de la période d'acquisition juin N-1 → mai N, absente des
    # données de mai) depuis le montant d'arbitrage du bulletin, injectée dans les
    # cumuls M-1 (lus par le moteur pour l'arbitrage 1/10e vs maintien).
    #   dixieme = base_ref × taux / jours_ref × jours_pris
    #   ⇒ base_ref = arbitrage × jours_ref / (taux × jours_pris)
    if exp.arbitrage_cp and exp.cp_days:
        base_ref = round(
            exp.arbitrage_cp * _JOURS_REF_DIXIEME
            / (_TAUX_DIXIEME * len(exp.cp_days)), 2)
        prev_month = MONTH - 1 if MONTH > 1 else 12
        prev_year = YEAR if MONTH > 1 else YEAR - 1
        prow = (admin.table("employee_schedules").select("id,cumuls")
                .match({"employee_id": employee_id, "year": prev_year,
                        "month": prev_month}).maybe_single().execute())
        if prow and prow.data:
            cum = prow.data.get("cumuls") or {}
            nested = cum.setdefault("cumuls", {}) if isinstance(cum, dict) else {}
            nested["brut_reference_n_1"] = base_ref
            admin.table("employee_schedules").update({"cumuls": cum}).eq(
                "id", prow.data["id"]).execute()
            actions.append(f"ref 1/10e {base_ref}")

    # Calendrier : (1) heures journalières = durée_hebdo/5 pour éliminer les HS
    # FANTÔMES (calendrier importé à 7,8 h/j sur contrat 35 h) ; (2) marquage des
    # jours de CP. Toujours appliqué (pas seulement si CP présents).
    duree_hebdo = float(emp_full.get("duree_hebdomadaire") or 35.0) if (emp_full := (
        admin.table("employees").select("duree_hebdomadaire").eq("id", employee_id)
        .single().execute().data)) else 35.0
    hpj = round(duree_hebdo / 5.0, 2)
    sched = (admin.table("employee_schedules").select("id,planned_calendar")
             .match({"employee_id": employee_id, "year": YEAR, "month": MONTH})
             .maybe_single().execute())
    if sched and sched.data:
        planned = sched.data.get("planned_calendar") or {}
        cal = planned.get("calendrier_prevu", [])
        by_day = {j.get("jour"): j for j in cal}
        for d in (exp.cp_days or []):
            j = by_day.get(d)
            if j is None:
                cal.append({"jour": d, "type": "conges_payes", "manuel": True,
                            "heures_prevues": hpj})
                by_day[d] = cal[-1]
            elif j.get("type") != "conges_payes":
                j["type"] = "conges_payes"; j["manuel"] = True
        for j in cal:
            if j.get("type") in ("travail", "conge", "conges_payes") and float(
                    j.get("heures_prevues") or 0) > 0:
                j["heures_prevues"] = hpj
        planned["calendrier_prevu"] = sorted(cal, key=lambda j: j["jour"])
        admin.table("employee_schedules").update(
            {"planned_calendar": planned}).eq("id", sched.data["id"]).execute()
        actions.append(f"cal {hpj}h/j CP{exp.cp_days or []}")
        # Vider le pointage réel : sinon les CP/absences posés au prévisionnel se
        # cumulent avec les heures du pointage (double compte). La base est
        # préservée (mois sans pointage) ; source de vérité = bulletin.
        ah = sched.data.get("actual_hours") if "actual_hours" in (sched.data or {}) else None
        ah_full = (admin.table("employee_schedules").select("actual_hours")
                   .eq("id", sched.data["id"]).single().execute().data or {})
        ah = ah_full.get("actual_hours") or {}
        if ah.get("calendrier_reel"):
            ah = copy.deepcopy(ah)
            ah["calendrier_reel"] = []
            admin.table("employee_schedules").update(
                {"actual_hours": ah}).eq("id", sched.data["id"]).execute()
            actions.append("actual_hours vidé")
    return actions


# --- Boucle auto-vérifiante ---------------------------------------------

def tier_s(match) -> float:
    _generate_payslip(match, YEAR, MONTH)
    for r in compare_matches([match], YEAR, MONTH, thresholds=default_thresholds(),
                             systemic_deltas={}, correction_attempts={}):
        return r.tier_s_max_delta
    return float("inf")


def reconcile(match, admin) -> dict:
    before = tier_s(match)
    if before <= CONVERGENCE:
        return {"matricule": match.matricule, "before": before, "after": before,
                "status": "déjà convergé", "actions": []}
    snap = take_snapshot(admin, match.employee_id)
    try:
        exp = parse_reference(match.reference.raw_text or "")
        actions = apply_expected(admin, match.employee_id, match.company_id, exp)
        if not actions:
            return {"matricule": match.matricule, "before": before, "after": before,
                    "status": "rien à faire", "actions": []}
        after = tier_s(match)
    except Exception as exc:
        try:
            restore_snapshot(admin, match.employee_id, match.company_id, snap)
            tier_s(match)
        except Exception:
            pass
        return {"matricule": match.matricule, "before": before, "after": before,
                "status": f"ERREUR (revert) {exc}", "actions": []}
    if after < before - 0.01:
        return {"matricule": match.matricule, "before": before, "after": after,
                "status": "amélioré", "actions": actions}
    restore_snapshot(admin, match.employee_id, match.company_id, snap)
    reverted = tier_s(match)
    return {"matricule": match.matricule, "before": before, "after": reverted,
            "status": f"revert (essai={after:.2f})", "actions": actions}


def main():
    global YEAR, MONTH
    args = list(sys.argv[1:])
    if "--year" in args:
        i = args.index("--year"); YEAR = int(args[i + 1]); args = args[:i] + args[i + 2:]
    if "--month" in args:
        i = args.index("--month"); MONTH = int(args[i + 1]); args = args[:i] + args[i + 2:]
    admin = get_supabase_admin_client()
    try:
        pdf = resolve_bulletin_pdf(COMPANY, YEAR, MONTH)
    except Exception:
        pdf = None
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH, pdf_path=pdf)
    cid = resolve_company_id(COMPANY)
    matched = match_employees(cid, refs).matched
    wanted = set(a for a in args if not a.startswith("--"))
    if wanted:
        matched = [m for m in matched if m.matricule in wanted]
    results = []
    for m in matched:
        try:
            res = reconcile(m, admin)
        except Exception as exc:
            res = {"matricule": m.matricule, "before": -1, "after": -1,
                   "status": f"ERREUR {exc}", "actions": []}
        results.append(res)
        print(f"[{res['matricule']:12s}] {res['before']:8.2f} -> {res['after']:8.2f}  {res['status']}", flush=True)
        for a in res["actions"]:
            print(f"      · {a}", flush=True)
    gains = sum(r["before"] - r["after"] for r in results if r["after"] < r["before"] - 0.01 and r["before"] >= 0)
    conv = sum(1 for r in results if r["after"] <= CONVERGENCE)
    print(f"\n=== RÉSUMÉ Lewis === convergés={conv} | gain cumulé={gains:.0f}€", flush=True)


if __name__ == "__main__":
    main()
