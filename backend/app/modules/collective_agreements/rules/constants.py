"""IDCC prioritaires pour l'extraction batch (lot 1 MVP)."""

PRIORITY_IDCC: list[str] = ["1486", "1090", "1516", "2098", "0044", "0292"]

SCHEMA_VERSION = 2

ZONE_TYPES = frozenset({"national", "regional", "departemental", "local", "inconnu"})

# IDCC connus pour grilles salariales régionales / départementales (BTP, TP…)
MULTI_ZONE_IDCC: frozenset[str] = frozenset(
    {"1596", "1597", "1702", "2609", "2420", "3212", "3213"}
)

# Conventions nationales volumineuses (métallurgie, etc.) : plus de textes salariaux / annexes
EXTENDED_SALARY_IDCC: frozenset[str] = frozenset(
    {"3248", "0547", "0685", "2247", "3109", "3127"}
)

MAX_SALARY_TEXTS_EXTENDED = 12
MAX_PAYROLL_ANNEXES_DEFAULT = 6
MAX_PAYROLL_ANNEXES_EXTENDED = 12

PRORATA_MODES = frozenset({"heures_contrat", "jours_forfait", "none"})

SANS_POINTAGE_POLICIES = frozenset({"plein_mois", "zero"})

BASE_CALCUL_METHODS = frozenset(
    {
        "salaire_minimum_conventionnel",
        "pourcentage_salaire_de_base",
        "valeur_du_point",
        "metallurgie_prime_anciennete",
    }
)

# IDCC avec barème SMH national (parser + seed déterministes)
SMH_NATIONAL_IDCC: frozenset[str] = frozenset({"3248"})

CONFIDENCE_LEVELS = frozenset({"high", "medium", "low"})

MAX_SCOUT_CHARS = 100_000
MAX_EXTRACTION_CHARS = 45_000
MAX_GRILLE_CHUNK_CHARS = 14_000
MAX_SALARY_TEXTS_DEFAULT = 3
MAX_SALARY_TEXTS_MULTI_ZONE = 30
MAX_SALARY_ZONES_MULTI = 16
MAX_GRILLE_EXTRACTION_CHUNKS = 18
MAX_PARALLEL_GRILLE_EXTRACTIONS = 4

KEYWORDS = (
    "ancienneté",
    "anciennete",
    "prime d'ancienneté",
    "prime d'anciennete",
    "grille",
    "classification",
    "coefficient",
    "minima",
    "minimum",
    "salaire minimum",
    "salaires minimaux",
    "rémunération minimale",
    "remuneration minimale",
    "textes salaires",
    "valeur du point",
    "positionnement",
    "annexe",
    "€",
    "euros",
)
