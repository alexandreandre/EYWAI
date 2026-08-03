"""Cache de très courte durée, pour éviter de relire la même chose N fois.

Les écrans de campagne bouclent sur les salariés et déclenchent plusieurs
calculs de solde par personne, chacun relisant le planning. La durée de vie
est volontairement de quelques secondes : elle couvre la durée d'une requête
HTTP sans jamais masquer durablement une saisie RH.
"""

from __future__ import annotations

import time
from typing import Any, Callable

DEFAULT_TTL_SECONDS = 5.0


class ShortLivedCache:
    def __init__(
        self,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._entries: dict[Any, tuple[float, Any]] = {}

    def get_or_load(self, key: Any, load: Callable[[Any], Any]) -> Any:
        now = self._clock()
        entry = self._entries.get(key)
        if entry is not None and now - entry[0] < self._ttl:
            return entry[1]
        value = load(key)
        self._entries[key] = (now, value)
        return value

    def clear(self) -> None:
        self._entries.clear()
