"""Version de la norme NEODeS selon le mois principal déclaré (registre R-454).

Sources ouvertes le 08/11/2026 : cahier technique 2027.1.3 et note différentielle
CT2026.1 → CT2027.1 (net-entreprises). Le journal de maintenance donne la P27V01
« en fonctionnement en janvier 2027 » ; une DSN d'un mois de 2026 reste en P26V01,
même déposée en janvier 2027.
"""

from __future__ import annotations

NORME_P26 = "P26V01"
NORME_P27 = "P27V01"

#: Dernière année dont le cahier technique est publié et lu.
_DERNIERE_ANNEE_CONNUE = 2027


def norme_de_la_periode(period: str) -> str:
    """Norme d'une DSN mensuelle « AAAA-MM ».

    Une année sans cahier lu est refusée : écrire la norme d'une autre année
    produirait un fichier faux sans le dire.
    """
    annee = int(period[:4])
    if annee > _DERNIERE_ANNEE_CONNUE:
        raise ValueError(
            f"Norme DSN de {annee} inconnue : le cahier technique de cette année "
            "reste à reporter dans Martine."
        )
    return NORME_P27 if annee == 2027 else NORME_P26


def porte_les_codes_ape(norme: str) -> bool:
    """S21.G00.06.003 et S21.G00.11.002 sont supprimées en P27V01 (note, § 11)."""
    return norme == NORME_P26


def porte_la_proratisation_du_plafond(norme: str) -> bool:
    """S21.G00.40.084 n'existe qu'à partir de la P27V01 (note, § 4.5)."""
    return norme != NORME_P26


def cet_patronale_sur_son_code(norme: str) -> bool:
    """P27V01 : la CET patronale quitte le 146 pour le 148 (note, § 8.2)."""
    return norme != NORME_P26
