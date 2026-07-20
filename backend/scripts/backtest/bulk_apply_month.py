"""Applique la reconstruction month-scoped (monthly_inputs + calendrier) SÉQUENTIELLEMENT
en écritures DB seulement (AUCUNE génération -> pas de race). Règle conditionnelle:
exclut les primes assiduité/présence si le mois a des CP/absences (prime conditionnelle
non payée en cas d'absence). Ne touche jamais le shared config. Fast.
Usage: bulk_apply_month.py <year> <month> [MATRICULE...]"""
import sys, copy
from collections import Counter
sys.path.insert(0,"/Users/alex/Desktop/EYWAI/EYWAI/backend")
from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
import scripts.backtest.mbc_reconcile as R
COMPANY="Mont Blanc Composite"
YEAR=int(sys.argv[1]); MONTH=int(sys.argv[2])
R.MONTH=MONTH; R.YEAR=YEAR
COND_KW=("assidu","presence","présence","présenc")
# Types de jours posés par ce script (marqués `manuel`) : remis à "travail" avant
# chaque application pour rendre l'outil IDEMPOTENT. Sans ce reset, `set_day` ne
# fait que convertir des jours et n'en restaure jamais : une passe antérieure au
# parsing plus large laissait des jours d'absence fantômes qu'aucune passe
# ultérieure n'effaçait (vécu : LABBE février gardait 20 jours d'arrêt d'un run
# précédent alors que le bulletin n'en porte que 10). `ferie` n'y figure pas —
# jamais posé par ce script, donc jamais réécrit.
MANAGED_DAY_TYPES=("conges_payes","absence_justifiee","absence_non_remuneree","arret_maladie")

def _heures_travail_reference(admin,eid):
    """heures_prevues d'un jour de travail du template pour ce salarié.

    Lue sur les jours `travail` NON manuels de tous ses mois (le backtest ne les
    touche jamais), d'où un repli fiable même si le mois courant n'a plus aucun
    jour travaillé intact (cas d'un arrêt couvrant tout le mois)."""
    rows=admin.table("employee_schedules").select("planned_calendar").eq("employee_id",eid).execute().data or []
    vals=Counter()
    for r in rows:
        for j in (r.get("planned_calendar") or {}).get("calendrier_prevu",[]):
            if j.get("type")=="travail" and not j.get("manuel") and j.get("heures_prevues"):
                vals[j["heures_prevues"]]+=1
    return vals.most_common(1)[0][0] if vals else 7.0

def apply_one(admin,eid,cid,exp):
    admin.table("monthly_inputs").delete().match({"employee_id":eid,"year":YEAR,"month":MONTH}).execute()
    rebuilt=[]
    def add(name,amount,*,taxed,taxable,qty=None):
        row={"employee_id":eid,"company_id":cid,"year":YEAR,"month":MONTH,"name":name,"amount":amount,"is_socially_taxed":taxed,"is_taxable":taxable}
        if qty is not None: row["payroll_quantity"]=qty
        rebuilt.append(row)
    for name,amount,qty in exp.primes_taxed:
        add(name,amount,taxed=True,taxable=True,qty=qty)
    for name,amount,qty in exp.primes_nontaxed:
        non_taxed=R.is_frais_pro_non_soumis_label(name)
        add(name,amount,taxed=not non_taxed,taxable=not non_taxed,qty=qty)
    if exp.participation is not None: add("Participation 2025 — numéraire",exp.participation,taxed=False,taxable=True)
    if exp.acompte is not None: add("Avance participation 2025 (déjà versée)",exp.acompte,taxed=False,taxable=False)
    if exp.acompte_salaire is not None: add(f"Acompte {MONTH:02d}/{YEAR}",-exp.acompte_salaire,taxed=False,taxable=False)
    if exp.cantine is not None: add("Cantine",exp.cantine,taxed=True,taxable=True)
    for name,amount in exp.prets: add(name,amount,taxed=False,taxable=False)
    for name,amount in exp.saisies: add(name,amount,taxed=False,taxable=False)
    # HS conjoncturelles (en sus des structurelles) : posees comme monthly_input
    # a quantite (le moteur calcule le montant), format identique a mai.
    if getattr(exp,"hs_conj_25",0.0):
        add("Heures supplémentaires conjoncturelles",0.0,taxed=True,taxable=True,qty=exp.hs_conj_25)
    if getattr(exp,"hs_conj_50",0.0):
        add("Heures supplémentaires conjoncturelles 50%",0.0,taxed=True,taxable=True,qty=exp.hs_conj_50)
    # Arrêt maladie AVEC maintien même mois : IJSS subrogée back-calculée
    # (= absence 100 % − maintien). Le libellé « IJSS override maintien »
    # déclenche `maintien_base_ouvree` + le forçage de l'IJSS (payslip_generator).
    arret_avec_maintien = bool(getattr(exp,"arret_days",None)) and getattr(exp,"ijss_override",None) is not None
    if arret_avec_maintien:
        add("IJSS override maintien",exp.ijss_override,taxed=False,taxable=False)
    for row in rebuilt: admin.table("monthly_inputs").insert(row).execute()
    # calendrier
    sched=(admin.table("employee_schedules").select("id,planned_calendar,actual_hours").match({"employee_id":eid,"year":YEAR,"month":MONTH}).maybe_single().execute())
    if sched and sched.data:
        arret_days=list(getattr(exp,"arret_days",None) or [])
        planned=sched.data.get("planned_calendar") or {}; cal=planned.get("calendrier_prevu",[])
        by_day={j.get("jour"):j for j in cal}; changed=False
        # Reset idempotent : tout jour posé par une passe antérieure repart de
        # "travail" avant d'appliquer le bulletin courant. Hors du garde
        # ci-dessous : un salarié dont le bulletin n'a PLUS d'absence doit voir
        # ses jours fantômes effacés, pas conservés.
        h_ref=None
        for j in cal:
            if j.get("manuel") and j.get("type") in MANAGED_DAY_TYPES:
                if h_ref is None: h_ref=_heures_travail_reference(admin,eid)
                j["type"]="travail"; j["heures_prevues"]=h_ref; j["manuel"]=False
                j.pop("arret_type",None); j.pop("subrogation_active",None)
                changed=True
        if exp.cp_days or exp.jtc_days or exp.absence_days or exp.absence_fractionnaire or arret_days:
            def set_day(day,nt,heures=7.5,arret_type=None,subrogation=None):
                nonlocal changed
                j=by_day.get(day)
                if j is None:
                    j={"jour":day,"type":nt,"manuel":True,"heures_prevues":heures}
                    cal.append(j); by_day[day]=j; changed=True
                elif j.get("type")!=nt:
                    j["type"]=nt; j["manuel"]=True
                    if nt=="absence_non_remuneree": j["heures_prevues"]=heures
                    elif not j.get("heures_prevues"): j["heures_prevues"]=heures
                    changed=True
                if nt=="arret_maladie":
                    # heures_prevues=0 → le moteur impute la réf. journalière
                    # légale (7 h temps plein), jamais 7,5 h (sur-déduction).
                    j["heures_prevues"]=0; j["arret_type"]=arret_type
                    if subrogation is not None: j["subrogation_active"]=subrogation
                    changed=True
            for d in exp.cp_days: set_day(d,"conges_payes")
            for d in exp.jtc_days:
                if d not in exp.cp_days: set_day(d,"absence_justifiee")
            for d in exp.absence_days:
                if d not in exp.cp_days and d not in exp.jtc_days: set_day(d,"absence_non_remuneree",heures=7.0)
            for d,h in exp.absence_fractionnaire:
                if d not in exp.cp_days and d not in exp.jtc_days: set_day(d,"absence_non_remuneree",heures=h)
            # Arrêt de travail. AVEC maintien même mois → arret_maladie en
            # SUBROGATION avec IJSS back-calculée : maintien_versé = cible −
            # IJSS_override, ce qui reproduit EXACTEMENT le maintien du bulletin
            # quel que soit le type de congé (maladie subrogée ; paternité/AT à
            # complément d'IJSS ; maternité 100 % → IJSS_override=0). On force
            # donc `maladie_simple` (mécanisme subrogation) plutôt que la branche
            # maternité 100 % inconditionnel du moteur, qui ignore l'IJSS et
            # sur-maintiendrait les paternités MBC (274,96 vs cible 1009,68).
            # SANS maintien (ou rappel cross-mois) → absence_non_remuneree 7 h :
            # pure retenue, aucun maintien fantôme injecté par le moteur.
            for d in arret_days:
                if arret_avec_maintien:
                    set_day(d,"arret_maladie",arret_type="maladie_simple",subrogation=True)
                else:
                    set_day(d,"absence_non_remuneree",heures=7.0)
        if changed:
            planned["calendrier_prevu"]=sorted(cal,key=lambda j:j["jour"])
            admin.table("employee_schedules").update({"planned_calendar":planned}).eq("id",sched.data["id"]).execute()
        ah=sched.data.get("actual_hours") or {}
        if ah.get("calendrier_reel"):
            ah=copy.deepcopy(ah); ah["calendrier_reel"]=[]
            admin.table("employee_schedules").update({"actual_hours":ah}).eq("id",sched.data["id"]).execute()
    return len(rebuilt)

def main():
    admin=get_supabase_admin_client()
    pdf=resolve_bulletin_pdf(COMPANY,YEAR,MONTH)
    refs=load_reference_bulletins(COMPANY,YEAR,MONTH,pdf_path=pdf)
    cid=resolve_company_id(COMPANY)
    matched=match_employees(cid,refs).matched
    matched.sort(key=lambda m:m.matricule)
    wanted=set(a for a in sys.argv[3:] if not a.startswith("--"))
    if wanted: matched=[m for m in matched if m.matricule in wanted]
    n=0
    for m in matched:
        try:
            exp=R.parse_reference(m.reference.raw_text or "")
            c=apply_one(admin,m.employee_id,m.company_id,exp); n+=1
            if n%15==0: print(f"  applied {n}/{len(matched)}...",flush=True)
        except Exception as e:
            print(f"[ERR {m.matricule}] {e}",flush=True)
    print(f"=== bulk apply month {MONTH:02d}: {n}/{len(matched)} employees ===",flush=True)

if __name__=="__main__": main()
