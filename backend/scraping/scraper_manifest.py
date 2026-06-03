"""
Manifeste unique des orchestrateurs scraping — source de vérité pour test_scrapers.py.

Chaque entrée décrit un orchestrateur, ses checks métier live et son tier de criticité.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Tier = Literal["critical", "standard", "static"]

AGIRC_ITEM_IDS = [
    "retraite_comp_t1",
    "retraite_comp_t2",
    "ceg_t1",
    "ceg_t2",
    "cet",
    "apec",
]


@dataclass(frozen=True)
class ScraperCheck:
    """Check métier sur la sortie JSON de l'orchestrateur (clé ``data``)."""

    path: list[str]
    min: float | None = None
    max: float | None = None
    year_current: bool = False
    not_null: bool = False
    keys_present: tuple[str, ...] = ()
    min_rows: int | None = None


@dataclass(frozen=True)
class ScraperEntry:
    name: str
    dir: str
    config_key: str
    orchestrator: str = "orchestrator.py"
    timeout: int = 120
    tier: Tier = "standard"
    dry_run: bool = True
    requires_selenium: bool = False
    network_flaky: bool = False
    checks: tuple[ScraperCheck, ...] = ()


def _patronal(min_v: float = 0.0, max_v: float = 0.5) -> tuple[ScraperCheck, ...]:
    return (ScraperCheck(path=["data", "patronal"], min=min_v, max=max_v),)


def _dual(keys: tuple[str, str], max_v: float = 0.5) -> tuple[ScraperCheck, ...]:
    return (
        ScraperCheck(path=["data", keys[0]], not_null=True, min=0.0, max=max_v),
        ScraperCheck(path=["data", keys[1]], not_null=True, min=0.0, max=max_v),
    )


def _vieillesse() -> tuple[ScraperCheck, ...]:
    return (
        ScraperCheck(path=["data", "plafonne"], min=0.0, max=0.2),
        ScraperCheck(path=["data", "deplafonne"], min=0.0, max=0.2),
    )


SCRAPER_MANIFEST: tuple[ScraperEntry, ...] = (
    ScraperEntry(
        name="SMIC",
        dir="SMIC",
        config_key="smic",
        timeout=180,
        tier="critical",
        checks=(
            ScraperCheck(path=["data", "cas_general"], min=10.0, max=15.0),
            ScraperCheck(path=["data", "annee"], year_current=True),
        ),
    ),
    ScraperEntry(
        name="PSS",
        dir="PSS",
        config_key="pss",
        timeout=180,
        tier="critical",
        checks=(
            ScraperCheck(path=["data", "annuel"], min=40000, max=60000),
            ScraperCheck(path=["data", "horaire"], not_null=True, min=20, max=35),
        ),
    ),
    ScraperEntry(
        name="PAS",
        dir="PAS",
        config_key="pas",
        timeout=300,
        tier="critical",
        checks=(ScraperCheck(path=["data"], not_null=True),),
    ),
    ScraperEntry(
        name="CSG",
        dir="CSG",
        config_key="cotisations",
        tier="critical",
        checks=(
            ScraperCheck(
                path=["data", "salarial", "non_deductible"],
                min=0.02,
                max=0.05,
            ),
            ScraperCheck(
                path=["data", "salarial", "deductible"],
                min=0.05,
                max=0.10,
            ),
        ),
    ),
    ScraperEntry(
        name="dialoguesocial",
        dir="dialoguesocial",
        config_key="cotisations",
        tier="critical",
        checks=(ScraperCheck(path=["data", "patronal"], min=0.0, max=0.001),),
    ),
    ScraperEntry(
        name="AGS",
        dir="AGS",
        config_key="cotisations",
        tier="critical",
        checks=_patronal(0.001, 0.01),
    ),
    ScraperEntry(
        name="CSA",
        dir="CSA",
        config_key="cotisations",
        tier="standard",
        checks=_patronal(0.0, 0.01),
    ),
    ScraperEntry(
        name="alloc",
        dir="alloc",
        config_key="cotisations",
        tier="critical",
        checks=_dual(("plein", "reduit")),
    ),
    ScraperEntry(
        name="assurancechomage",
        dir="assurancechomage",
        config_key="cotisations",
        tier="standard",
        checks=_patronal(0.02, 0.05),
    ),
    ScraperEntry(
        name="vieillessepatronal",
        dir="vieillessepatronal",
        config_key="cotisations",
        tier="critical",
        checks=_vieillesse(),
    ),
    ScraperEntry(
        name="vieillessesalarial",
        dir="vieillessesalarial",
        config_key="cotisations",
        tier="critical",
        checks=_vieillesse(),
    ),
    ScraperEntry(
        name="CFP",
        dir="CFP",
        config_key="cotisations",
        tier="standard",
        checks=_dual(("moins_11", "plus_11"), max_v=0.02),
    ),
    ScraperEntry(
        name="FNAL",
        dir="FNAL",
        config_key="cotisations",
        tier="standard",
        checks=_dual(("moins_50", "plus_50"), max_v=0.01),
    ),
    ScraperEntry(
        name="MMIDpatronal",
        dir="MMIDpatronal",
        config_key="cotisations",
        tier="critical",
        checks=_dual(("plein", "reduit")),
    ),
    ScraperEntry(
        name="MMIDsalarial",
        dir="MMIDsalarial",
        config_key="cotisations",
        tier="standard",
        checks=(ScraperCheck(path=["data", "alsace"], min=0.0, max=0.05),),
    ),
    ScraperEntry(
        name="AGIRC-ARRCO",
        dir="AGIRC-ARRCO",
        config_key="cotisations",
        timeout=180,
        tier="critical",
        checks=(
            ScraperCheck(
                path=["data"],
                keys_present=tuple(AGIRC_ITEM_IDS),
            ),
        ),
    ),
    ScraperEntry(
        name="taxeapprentissage",
        dir="taxeapprentissage",
        config_key="cotisations",
        tier="standard",
        checks=(
            ScraperCheck(path=["data", "total", "taux_metropole"], min=0.0, max=0.01),
        ),
    ),
    ScraperEntry(
        name="PREVOYANCE_CADRE",
        dir="prevoyance",
        config_key="cotisations",
        orchestrator="orchestrator_cadre.py",
        tier="standard",
        checks=(
            ScraperCheck(path=["data", "valeurs", "patronal"], min=0.01, max=0.03),
        ),
    ),
    ScraperEntry(
        name="PREVOYANCE_NON_CADRE",
        dir="prevoyance",
        config_key="cotisations",
        orchestrator="orchestrator_non_cadre.py",
        tier="standard",
        checks=(ScraperCheck(path=["data"], not_null=True),),
    ),
    ScraperEntry(
        name="IJmaladie",
        dir="IJmaladie",
        config_key="ij_plafonds",
        timeout=300,
        tier="standard",
        checks=(
            ScraperCheck(path=["data", "maladie"], min=35, max=500),
            ScraperCheck(path=["data", "maternite_paternite"], min=35, max=500),
        ),
    ),
    ScraperEntry(
        name="fraispro",
        dir="fraispro",
        config_key="frais_pro",
        timeout=180,
        tier="standard",
        checks=(
            ScraperCheck(path=["data", "sections", "repas", "sur_lieu_travail"], min=1, max=20),
        ),
    ),
    ScraperEntry(
        name="Avantages",
        dir="Avantages",
        config_key="avantages_en_nature",
        timeout=180,
        tier="standard",
        checks=(ScraperCheck(path=["data", "repas"], min=1, max=20),),
    ),
    ScraperEntry(
        name="bareme-indemnite-kilometrique",
        dir="bareme-indemnite-kilometrique",
        config_key="baremes_km",
        timeout=180,
        tier="standard",
        checks=(
            ScraperCheck(path=["data", "annee"], year_current=True),
            ScraperCheck(path=["data", "vehicules", "voitures"], not_null=True),
        ),
    ),
    ScraperEntry(
        name="VM",
        dir="versement_mobilite",
        config_key="taux_vmrr",
        timeout=300,
        tier="standard",
        network_flaky=True,
        checks=(ScraperCheck(path=["data", "rows"], min_rows=100),),
    ),
    ScraperEntry(
        name="heuressupp",
        dir="heuressupp",
        config_key="heures_supp",
        tier="static",
        checks=(
            ScraperCheck(path=["data", "majoration_hs_25"], min=0.1, max=0.5),
            ScraperCheck(path=["data", "majoration_hs_50"], min=0.3, max=0.8),
        ),
    ),
    ScraperEntry(
        name="primes",
        dir="primes",
        config_key="primes",
        tier="static",
        checks=(ScraperCheck(path=["data"], not_null=True),),
    ),
)


def get_manifest(
    *,
    tier: Tier | None = None,
    only: set[str] | None = None,
) -> list[ScraperEntry]:
    """Filtre le manifeste par tier et/ou noms."""
    out: list[ScraperEntry] = []
    for entry in SCRAPER_MANIFEST:
        if tier and entry.tier != tier:
            continue
        if only and entry.name not in only:
            continue
        out.append(entry)
    return out


def manifest_names() -> set[str]:
    return {e.name for e in SCRAPER_MANIFEST}


def tier_for(scraper_name: str) -> Tier:
    """Tier d'un scraper d'après le manifeste (source de vérité). Défaut: standard."""
    for entry in SCRAPER_MANIFEST:
        if entry.name == scraper_name:
            return entry.tier
    return "standard"


def checks_for(scraper_name: str) -> tuple[ScraperCheck, ...]:
    """Invariants structurels (ScraperCheck) d'un scraper d'après le manifeste."""
    for entry in SCRAPER_MANIFEST:
        if entry.name == scraper_name:
            return entry.checks
    return ()
