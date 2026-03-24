# Shared kernel: types, result, primitives communes.
from app.shared.kernel.types import T, UUID_STR
from app.shared.kernel.result import Err, Ok, Result, is_err, is_ok

__all__ = [
    "T",
    "UUID_STR",
    "Ok",
    "Err",
    "Result",
    "is_ok",
    "is_err",
]
