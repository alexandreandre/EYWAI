"""Heure murale de l'entreprise (Europe/Paris).

Les pointages sont stockés en instants (timestamptz) — la vérité absolue.
Mais tout ce qui raisonne en « heure de la journée » (créneaux, tolérances,
heures sup, regroupement par jour) doit se faire en heure MURALE : un badge
de 8 h à Paris stocké 06:00 UTC l'été n'est pas une entrée en avance.

Poser `TZ=` sur le conteneur n'est pas un correctif : le comportement des
écritures naïves dépendrait alors du fuseau de la machine. La conversion
est explicite, ici, et nulle part ailleurs.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

FUSEAU_ENTREPRISE = ZoneInfo("Europe/Paris")


def en_heure_locale(ts: datetime) -> datetime:
    """Instant → heure murale Europe/Paris.

    Un timestamp naïf est supposé UTC : les anciens ``datetime.now()`` sur
    l'horloge du conteneur (UTC sur Cloud Run) ont produit ces valeurs.
    """
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(FUSEAU_ENTREPRISE)


def date_locale(ts: datetime) -> date:
    """Jour civil de l'entreprise auquel appartient cet instant."""
    return en_heure_locale(ts).date()


def aujourd_hui_local() -> date:
    """La date « d'aujourd'hui » vue de l'entreprise."""
    return datetime.now(FUSEAU_ENTREPRISE).date()


def maintenant_utc() -> datetime:
    """Instant présent, aware UTC — pour les écritures en base."""
    return datetime.now(timezone.utc)


def fenetre_jour_local(jour: date) -> tuple[datetime, datetime]:
    """[minuit, 23:59:59.999999] du jour PARIS, en instants aware."""
    debut = datetime.combine(jour, datetime.min.time(), tzinfo=FUSEAU_ENTREPRISE)
    fin = datetime.combine(jour, datetime.max.time(), tzinfo=FUSEAU_ENTREPRISE)
    return debut, fin
