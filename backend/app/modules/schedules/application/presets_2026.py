"""
Presets 2026 — bibliothèque déclarative de modèles horaires + plans par société.

IMPORTANT : ce module ne contient que des DONNÉES (règles remontées par Elsa et le
client Cartol), aucune logique de paie. `apply_preset` matérialise ces données en
vrais enregistrements `company_week_schedule_templates` + `company_schedule_plans`,
que les RH peuvent ensuite créer / modifier / dupliquer / désactiver depuis l'UI.
Aucune règle société n'est cachée dans le moteur paie.

Notation :
- Comitech/Colorplast/MBC/Lewis utilisent des heures décimales (« 8,5 » = 8.5).
- Cartol utilise la notation HHhMM (« 7h50 » = 7 h 50 min), convertie via `hhmm`.
  Le total réel recalculé depuis les jours peut légèrement différer du nominal
  annoncé (ex. 35 h) : on le signale via `needs_confirmation` plutôt que de figer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.modules.schedules.domain.calendar_generation_rules import (
    hhmm,
    week_weekly_hours,
)
from app.modules.schedules.domain.break_policy import INDUSTRIAL_2X10_MEAL_30


# ----- helpers de construction -----


def _day(
    iso: int,
    hours: float,
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    brk: int = 0,
    paid: bool = False,
    breaks: Optional[List[Dict[str, Any]]] = None,
    comment: Optional[str] = None,
    day_type: str = "travail",
) -> Dict[str, Any]:
    row = {
        "day": iso,
        "type": day_type,
        "hours": round(float(hours), 4),
        "start": start,
        "end": end,
        "break_minutes": brk,
        "break_paid": paid,
        "comment": comment,
    }
    if breaks:
        row["breaks"] = breaks
    return row


def _industrial_work_day(
    iso: int,
    *,
    hours: float = 7.5,
    start: str = "08:00",
    end: str = "16:00",
) -> Dict[str, Any]:
    """Journée type 2×10 min payées + 30 min repas (net contractuel)."""
    return _day(
        iso,
        hours,
        start=start,
        end=end,
        breaks=[dict(b) for b in INDUSTRIAL_2X10_MEAL_30],
    )


@dataclass
class TemplateSpec:
    name: str
    days: List[Dict[str, Any]]
    description: str = ""
    modulation_tier: str = "neutral"


@dataclass
class PlanSpec:
    name: str
    template_names: List[str]              # cycle ordonné (1 = pas d'alternance)
    scope_type: str = "company"            # company | team | service | employees
    employee_names: List[str] = field(default_factory=list)
    start_date: str = "2026-01-01"
    end_date: Optional[str] = None
    cycle_anchor: Optional[str] = None
    overwrite_mode: str = "preserve_manual"
    needs_confirmation: bool = False
    notes: str = ""


@dataclass
class Preset:
    key: str
    company_label: str
    templates: List[TemplateSpec]
    plans: List[PlanSpec]


# ----- définition des presets -----


def _uniform(hours: float, days: List[int] = [1, 2, 3, 4, 5], **kw: Any) -> List[Dict[str, Any]]:
    return [_day(d, hours, **kw) for d in days]


def _build_registry() -> Dict[str, Preset]:
    presets: Dict[str, Preset] = {}

    # ---------- Comitech Composite ----------
    comitech_ete = TemplateSpec(
        name="Comitech — Été (39h)",
        description="Heure d'été : L-J 8h, V 7h = 39h/semaine. Dates d'été à confirmer avec Elsa.",
        days=[_day(1, 8), _day(2, 8), _day(3, 8), _day(4, 8), _day(5, 7)],
    )
    comitech_hiver = TemplateSpec(
        name="Comitech — Hiver (39h)",
        description="Heure d'hiver : L/Ma/J 8,5h, Me 8h, V 5,5h = 39h/semaine.",
        days=[_day(1, 8.5), _day(2, 8.5), _day(3, 8), _day(4, 8.5), _day(5, 5.5)],
    )
    presets["comitech"] = Preset(
        key="comitech",
        company_label="Comitech Composite",
        templates=[comitech_ete, comitech_hiver],
        plans=[
            PlanSpec(
                name="Comitech — Hiver 2026",
                template_names=[comitech_hiver.name],
                scope_type="company",
                start_date="2026-01-01",
                end_date="2026-12-31",
                notes="Modèle hiver appliqué par défaut. Activer l'été via le plan dédié.",
            ),
            PlanSpec(
                name="Comitech — Été 2026 (à activer)",
                template_names=[comitech_ete.name],
                scope_type="company",
                start_date="2026-04-01",
                end_date="2026-10-31",
                needs_confirmation=True,
                notes="Dates exactes de l'heure d'été à confirmer avec Elsa avant génération.",
            ),
        ],
    )

    # ---------- Colorplast ----------
    colorplast = TemplateSpec(
        name="Colorplast — Standard (39h)",
        description="L-J 8,5h, V 5h = 39h/semaine.",
        days=[_day(1, 8.5), _day(2, 8.5), _day(3, 8.5), _day(4, 8.5), _day(5, 5)],
    )
    presets["colorplast"] = Preset(
        key="colorplast",
        company_label="Colorplast",
        templates=[colorplast],
        plans=[
            PlanSpec(
                name="Colorplast — 2026",
                template_names=[colorplast.name],
                scope_type="company",
                start_date="2026-01-01",
                end_date="2026-12-31",
            )
        ],
    )

    # ---------- MBC ----------
    mbc_std = TemplateSpec(
        name="MBC — Standard (37,5h)",
        description="L-V 7,5h = 37,5h/semaine.",
        days=_uniform(7.5),
    )
    mbc_3x8 = TemplateSpec(
        name="MBC — 3×8 pauses (37,5h)",
        description=(
            "2×10 min payées (incluses) + 30 min repas non payée. "
            "Net 7,5 h/jour — horaires indicatifs journée 08h–16h."
        ),
        days=[_industrial_work_day(d) for d in [1, 2, 3, 4, 5]],
    )
    mbc_rina = TemplateSpec(
        name="MBC — Rina LIKA (20h)",
        description="L-V 4h = 20h/semaine.",
        days=_uniform(4),
    )
    mbc_sihem = TemplateSpec(
        name="MBC — Sihem RABBENI (17,5h)",
        description="L-V 3,5h = 17,5h/semaine.",
        days=_uniform(3.5),
    )
    presets["mbc"] = Preset(
        key="mbc",
        company_label="MBC",
        templates=[mbc_std, mbc_3x8, mbc_rina, mbc_sihem],
        plans=[
            PlanSpec(
                name="MBC — Standard 2026",
                template_names=[mbc_std.name],
                scope_type="company",
                start_date="2026-01-01",
                end_date="2026-07-31",
            ),
            PlanSpec(
                name="MBC — Pauses août 2026",
                template_names=[mbc_3x8.name],
                scope_type="company",
                start_date="2026-08-01",
                end_date="2026-12-31",
                notes=(
                    "Courrier employeur 01/06/2026 : 2×10 min payées + 30 min repas. "
                    "Appliquer aussi le preset pointage « 3×8 industriel »."
                ),
            ),
            PlanSpec(
                name="MBC — Rina LIKA 2026",
                template_names=[mbc_rina.name],
                scope_type="employees",
                employee_names=["Rina LIKA"],
                start_date="2026-01-01",
                end_date="2026-12-31",
            ),
            PlanSpec(
                name="MBC — Sihem RABBENI 2026",
                template_names=[mbc_sihem.name],
                scope_type="employees",
                employee_names=["Sihem RABBENI"],
                start_date="2026-01-01",
                end_date="2026-12-31",
            ),
        ],
    )

    # ---------- Lewis ----------
    lewis_partiel = TemplateSpec(
        name="Lewis — Activité partielle (35h)",
        description="Juin-août 2026 : L-V 7h = 35h/semaine.",
        days=_uniform(7),
    )
    # Cycle 70h/2 semaines — répartition raisonnable, ambiguïté « 7,45 » NON figée.
    lewis_a = TemplateSpec(
        name="Lewis — Semaine A (37,25h)",
        description="Cycle 70h/2sem, semaine A = 37,25h. Répartition à confirmer (ambiguïté « 7,45 »).",
        days=[_day(1, 8), _day(2, 8), _day(3, 8), _day(4, 8), _day(5, 5.25)],
    )
    lewis_b = TemplateSpec(
        name="Lewis — Semaine B (32,75h)",
        description="Cycle 70h/2sem, semaine B = 32,75h. Répartition à confirmer (ambiguïté « 7,45 »).",
        days=[_day(1, 7), _day(2, 7), _day(3, 7), _day(4, 7), _day(5, 4.75)],
    )
    presets["lewis"] = Preset(
        key="lewis",
        company_label="Lewis",
        templates=[lewis_partiel, lewis_a, lewis_b],
        plans=[
            PlanSpec(
                name="Lewis — Activité partielle été 2026",
                template_names=[lewis_partiel.name],
                scope_type="company",
                start_date="2026-06-01",
                end_date="2026-08-31",
                needs_confirmation=True,
                notes="Activité partielle : 7h travaillées OU référence avant heures chômées ? À confirmer.",
            ),
            PlanSpec(
                name="Lewis — Cycle 70h/2sem (après août 2026)",
                template_names=[lewis_a.name, lewis_b.name],
                scope_type="company",
                start_date="2026-09-01",
                end_date="2026-12-31",
                cycle_anchor="2026-08-31",  # lundi d'ancrage semaine A
                needs_confirmation=True,
                notes="Cible 70h/2sem. Répartition A/B à valider ; « 7,45 » = 7,45h décimal ou 7h45 ?",
            ),
        ],
    )

    # ---------- Cartol ----------
    presets["cartol"] = _build_cartol()

    return presets


def _build_cartol() -> Preset:
    # Atelier 35H : L-J 7h50 (08-12/13-17, pause 10min), V 3h45 (08-11h45).
    atelier_35 = TemplateSpec(
        name="Cartol — Atelier 35H",
        description="Journée standard atelier. Nominal 35h (somme réelle ≈35,08h).",
        days=[
            _day(1, hhmm(7, 50), start="08:00", end="17:00", brk=10),
            _day(2, hhmm(7, 50), start="08:00", end="17:00", brk=10),
            _day(3, hhmm(7, 50), start="08:00", end="17:00", brk=10),
            _day(4, hhmm(7, 50), start="08:00", end="17:00", brk=10),
            _day(5, hhmm(3, 45), start="08:00", end="11:45"),
        ],
    )
    # Atelier Équipe Matin : L-J 05-13h15, V 05-12h, pause 30min → net 37h30.
    atelier_matin = TemplateSpec(
        name="Cartol — Atelier Équipe Matin",
        description="Équipe du matin / selon nécessité. Nominal 7h30/jour ; net horaires = 37h30.",
        days=[
            _day(1, hhmm(7, 45), start="05:00", end="13:15", brk=30),
            _day(2, hhmm(7, 45), start="05:00", end="13:15", brk=30),
            _day(3, hhmm(7, 45), start="05:00", end="13:15", brk=30),
            _day(4, hhmm(7, 45), start="05:00", end="13:15", brk=30),
            _day(5, hhmm(6, 30), start="05:00", end="12:00", brk=30),
        ],
    )
    # Atelier Été : 06-14, pause 30min → 7h30/jour, 37h30. Horaires au choix salarié.
    atelier_ete = TemplateSpec(
        name="Cartol — Atelier Été",
        description="Fortes chaleurs. 06-14 pause 30min = 7h30/jour, 37h30. Horaires au choix des salariés.",
        days=_uniform(7.5, start="06:00", end="14:00", brk=30),
    )
    # Atelier Spécifique Loic Hauchecorne : 08-12/13-16h40 pause 10min = 7h30, 37h30.
    atelier_loic = TemplateSpec(
        name="Cartol — Atelier Spécifique (Loic Hauchecorne)",
        description="Forte variation réelle selon la cataphorèse. 08-12/13-16h40 pause 10min = 7h30/jour.",
        days=_uniform(7.5, start="08:00", end="16:40", brk=10),
    )
    # Atelier 28H MN Deplanne : L repos, Ma-J 7h50, V 4h25.
    atelier_28 = TemplateSpec(
        name="Cartol — Atelier 28H (MN Deplanne)",
        description="Lundi non travaillé. Ma-J 7h50 (08-12/13-17 pause 10min), V 4h25 (08-12h25). Nominal 28h.",
        days=[
            _day(2, hhmm(7, 50), start="08:00", end="17:00", brk=10),
            _day(3, hhmm(7, 50), start="08:00", end="17:00", brk=10),
            _day(4, hhmm(7, 50), start="08:00", end="17:00", brk=10),
            _day(5, hhmm(4, 25), start="08:00", end="12:25"),
        ],
    )
    # Atelier 20H Michèle Cesbron : L-V 4h (08-12).
    atelier_20 = TemplateSpec(
        name="Cartol — Atelier 20H (Michèle Cesbron)",
        description="Agent d'entretien. L-V 4h = 20h/semaine (08-12).",
        days=_uniform(4, start="08:00", end="12:00"),
    )
    # Bureau 35H Dorian Morin / Julien Camenen : L-J 7h50 (08-12/13-17h10 pause 20), V 3h50 (08-12 pause 10).
    bureau_35 = TemplateSpec(
        name="Cartol — Bureau 35H",
        description="L-J 08-12/13-17h10 pause 20min, V 08-12 pause 10min. Nominal 35h.",
        days=[
            _day(1, hhmm(7, 50), start="08:00", end="17:10", brk=20),
            _day(2, hhmm(7, 50), start="08:00", end="17:10", brk=20),
            _day(3, hhmm(7, 50), start="08:00", end="17:10", brk=20),
            _day(4, hhmm(7, 50), start="08:00", end="17:10", brk=20),
            _day(5, hhmm(3, 50), start="08:00", end="12:00", brk=10),
        ],
    )
    # Bureau 35H Spécifique Emilie Vignaud : alternance demi-journée mercredi / vendredi.
    bureau_emilie_a = TemplateSpec(
        name="Cartol — Bureau 35H Emilie (semaine vendredi court)",
        description="Alternance A : demi-journée le vendredi. Modifiable par les RH.",
        days=[
            _day(1, hhmm(7, 50), start="08:00", end="17:10", brk=20),
            _day(2, hhmm(7, 50), start="08:00", end="17:10", brk=20),
            _day(3, hhmm(7, 50), start="08:00", end="17:10", brk=20),
            _day(4, hhmm(7, 50), start="08:00", end="17:10", brk=20),
            _day(5, hhmm(3, 50), start="08:00", end="12:00", brk=10),
        ],
    )
    bureau_emilie_b = TemplateSpec(
        name="Cartol — Bureau 35H Emilie (semaine mercredi court)",
        description="Alternance B : demi-journée le mercredi. Modifiable par les RH.",
        days=[
            _day(1, hhmm(7, 50), start="08:00", end="17:10", brk=20),
            _day(2, hhmm(7, 50), start="08:00", end="17:10", brk=20),
            _day(3, hhmm(3, 50), start="08:00", end="12:00", brk=10),
            _day(4, hhmm(7, 50), start="08:00", end="17:10", brk=20),
            _day(5, hhmm(7, 50), start="08:00", end="17:10", brk=20),
        ],
    )
    # Bureau 35H Spécifique Tania Espirito Santo : total 35h exact.
    bureau_tania = TemplateSpec(
        name="Cartol — Bureau 35H (Tania Espirito Santo)",
        description="L/Ma/J 7h50, Me 4h50, V 6h40 = 35h.",
        days=[
            _day(1, hhmm(7, 50), start="08:00", end="17:10", brk=20),
            _day(2, hhmm(7, 50), start="08:00", end="17:10", brk=20),
            _day(3, hhmm(4, 50), start="08:00", end="13:00", brk=10),
            _day(4, hhmm(7, 50), start="08:00", end="17:10", brk=20),
            _day(5, hhmm(6, 40), start="08:00", end="16:00", brk=20),
        ],
    )
    # Bureau Été : 06-14 pause 40min = 7h20/jour, 36h40. Horaires au choix salarié.
    bureau_ete = TemplateSpec(
        name="Cartol — Bureau Été",
        description="Fortes chaleurs. 06-14 pause 40min = 7h20/jour, 36h40. Horaires au choix des salariés.",
        days=_uniform(hhmm(7, 20), start="06:00", end="14:00", brk=40),
    )
    # Bureau Secrétariat de direction Corinne Verger : 7h30/jour = 37h30.
    bureau_secretariat = TemplateSpec(
        name="Cartol — Bureau Secrétariat de direction (Corinne Verger)",
        description="08-12/13-16h30 = 7h30/jour, 37h30/semaine.",
        days=_uniform(7.5, start="08:00", end="16:30"),
    )
    # Usage 40h (peinture/maintenance/ferrage) — variante temporaire, périmètre à confirmer.
    atelier_40 = TemplateSpec(
        name="Cartol — Usage 40H (vendredi après-midi)",
        description="Usage 40h (peinture/maintenance/ferrage). Périmètre et salariés à confirmer.",
        days=[
            _day(1, 8, start="08:00", end="17:00", brk=10),
            _day(2, 8, start="08:00", end="17:00", brk=10),
            _day(3, 8, start="08:00", end="17:00", brk=10),
            _day(4, 8, start="08:00", end="17:00", brk=10),
            _day(5, 8, start="08:00", end="17:00", brk=10),
        ],
    )

    templates = [
        atelier_35, atelier_matin, atelier_ete, atelier_loic, atelier_28,
        atelier_20, bureau_35, bureau_emilie_a, bureau_emilie_b, bureau_tania,
        bureau_ete, bureau_secretariat, atelier_40,
    ]

    def _plan(name, tmpls, emp=None, need=False, note="", anchor=None):
        return PlanSpec(
            name=name,
            template_names=[t.name for t in tmpls],
            scope_type="employees" if emp else "company",
            employee_names=emp or [],
            start_date="2026-01-01",
            end_date="2026-12-31",
            cycle_anchor=anchor,
            needs_confirmation=need,
            notes=note,
        )

    plans = [
        _plan("Cartol — Atelier 35H 2026", [atelier_35], need=True,
              note="Nominal 35h vs somme réelle HHhMM ≈35,08h : réconciliation à confirmer."),
        _plan("Cartol — Atelier Équipe Matin 2026", [atelier_matin], need=True,
              note="Nominal 7h30/jour vs horaires (net 37h30) : à confirmer."),
        _plan("Cartol — Atelier Été 2026", [atelier_ete], need=True,
              note="Horaires d'été au choix des salariés : période et affectation à confirmer."),
        _plan("Cartol — Atelier Spécifique Loic Hauchecorne 2026", [atelier_loic],
              emp=["Loic Hauchecorne"]),
        _plan("Cartol — Atelier 28H MN Deplanne 2026", [atelier_28],
              emp=["MN Deplanne"], need=True,
              note="Nominal 28h vs somme réelle : réconciliation à confirmer."),
        _plan("Cartol — Atelier 20H Michèle Cesbron 2026", [atelier_20],
              emp=["Michèle Cesbron"]),
        _plan("Cartol — Bureau 35H 2026", [bureau_35],
              emp=["Dorian Morin", "Julien Camenen"], need=True,
              note="Nominal 35h vs somme réelle : réconciliation à confirmer."),
        _plan("Cartol — Bureau 35H Emilie Vignaud 2026 (alternance)",
              [bureau_emilie_a, bureau_emilie_b], emp=["Emilie Vignaud"],
              anchor="2025-12-29", need=True,
              note="Alternance mercredi/vendredi court : ancrage et ordre A/B à confirmer."),
        _plan("Cartol — Bureau 35H Tania Espirito Santo 2026", [bureau_tania],
              emp=["Tania Espirito Santo"]),
        _plan("Cartol — Bureau Été 2026", [bureau_ete], need=True,
              note="Horaires d'été au choix des salariés : période et affectation à confirmer."),
        _plan("Cartol — Bureau Secrétariat Corinne Verger 2026", [bureau_secretariat],
              emp=["Corinne Verger"]),
        # Bureau Forfaitaire : PAS de conversion auto en heures. Alerte RH.
        PlanSpec(
            name="Cartol — Bureau Forfaitaire (à vérifier)",
            template_names=[],
            scope_type="employees",
            employee_names=[
                "Christophe Penaud", "Jocelyn Frouin", "Tanguy Cotillon", "Damien Faucher",
            ],
            start_date="2026-01-01",
            end_date="2026-12-31",
            needs_confirmation=True,
            notes="Forfaits jours/spécifiques : NE PAS convertir en heures prévues. Vérifier le statut salarié.",
        ),
        _plan("Cartol — Usage 40H peinture/maintenance/ferrage (à confirmer)", [atelier_40],
              need=True,
              note="Usage 40h (vendredi après-midi ou embauche 07h) : périmètre et salariés à confirmer."),
    ]

    return Preset(
        key="cartol", company_label="Cartol", templates=templates, plans=plans
    )


_REGISTRY: Optional[Dict[str, Preset]] = None


def get_registry() -> Dict[str, Preset]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY


def list_presets() -> List[Dict[str, Any]]:
    """Résumé des presets pour l'UI RH (modèles + plans + totaux recalculés)."""
    out: List[Dict[str, Any]] = []
    for preset in get_registry().values():
        out.append(
            {
                "key": preset.key,
                "company_label": preset.company_label,
                "templates": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "weekly_hours": week_weekly_hours(t.days),
                        "day_configs": t.days,
                    }
                    for t in preset.templates
                ],
                "plans": [
                    {
                        "name": p.name,
                        "scope_type": p.scope_type,
                        "employee_names": p.employee_names,
                        "template_names": p.template_names,
                        "start_date": p.start_date,
                        "end_date": p.end_date,
                        "cycle_anchor": p.cycle_anchor,
                        "needs_confirmation": p.needs_confirmation,
                        "notes": p.notes,
                    }
                    for p in preset.plans
                ],
            }
        )
    return out


__all__ = [
    "Preset",
    "TemplateSpec",
    "PlanSpec",
    "get_registry",
    "list_presets",
]
