"""Types Pydantic partagés par les schémas de réponse.

`Montant` : un décimal validé en `Decimal` (précision des montants), mais
rendu en NOMBRE dans le JSON. Par défaut Pydantic sérialise un `Decimal` en
chaîne (« "46.49" ») ; le frontend, qui déclare ces champs `number`,
appelait `toFixed` sur une chaîne et la page Saisies sur salaire tombait en
écran blanc (Gautheron, 12/09/2026).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

Montant = Annotated[
    Decimal,
    PlainSerializer(lambda v: float(v), return_type=float, when_used="json"),
]
