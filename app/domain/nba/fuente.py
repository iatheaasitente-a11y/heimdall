"""Contrato mínimo para consultar datos NBA sin acoplarse a un proveedor."""

from typing import Protocol


class FuenteNBA(Protocol):
    """Fuente intercambiable de consultas NBA."""

    def consultar(self, consulta: str) -> str:
        """Resuelve una consulta y devuelve el resultado como texto."""
