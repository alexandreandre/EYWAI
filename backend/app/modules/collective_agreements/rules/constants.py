"""IDCC prioritaires pour l'extraction batch (lot 1 MVP)."""

PRIORITY_IDCC: list[str] = ["1486", "1090", "1516", "2098", "0044"]

SCHEMA_VERSION = 1

BASE_CALCUL_METHODS = frozenset(
    {
        "salaire_minimum_conventionnel",
        "pourcentage_salaire_de_base",
    }
)

CONFIDENCE_LEVELS = frozenset({"high", "medium", "low"})

MAX_SCOUT_CHARS = 100_000
MAX_EXTRACTION_CHARS = 45_000

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
