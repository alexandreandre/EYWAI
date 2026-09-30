"""Piège à écritures : toute écriture postgrest ou storage lève EcritureInterdite.

À poser AVANT d'importer l'application. Réversible, pour que les tests ne fuient pas.
"""
from __future__ import annotations

ECRITURES: list[str] = []
_ORIGINAUX: dict[tuple[type, str], object] = {}


class EcritureInterdite(RuntimeError):
    """Une vérification a tenté d'écrire : rien n'est parti."""


def _cibles():
    import postgrest._sync.request_builder as rb
    import storage3._sync.file_api as fa

    return [(rb.SyncRequestBuilder, n) for n in ("insert", "update", "upsert", "delete")] + [
        (fa.SyncBucketActionsMixin, n) for n in ("upload", "update", "remove", "move", "copy")
    ]


def poser_le_piege() -> None:
    for cls, nom in _cibles():
        if (cls, nom) in _ORIGINAUX:
            continue
        _ORIGINAUX[(cls, nom)] = getattr(cls, nom)

        def piege(self, *a, _nom=nom, _cls=cls, **k):
            cible = str(getattr(self, "path", None) or getattr(self, "id", None) or "")
            ECRITURES.append(f"{_cls.__name__}.{_nom} {cible.split('/')[-1]}".replace(f"{_cls.__name__}.", ""))
            raise EcritureInterdite(f"écriture interdite : {_cls.__name__}.{_nom} ({cible})")

        piege._piege = True
        setattr(cls, nom, piege)


def retirer_le_piege() -> None:
    for (cls, nom), original in list(_ORIGINAUX.items()):
        setattr(cls, nom, original)
        del _ORIGINAUX[(cls, nom)]
