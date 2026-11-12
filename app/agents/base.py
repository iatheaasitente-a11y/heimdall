"""Contrato común de los agentes."""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from uuid import UUID


class AgenteBase(ABC):
    """Interfaz para agentes que procesan mensajes de un usuario."""

    @abstractmethod
    def procesar(
        self,
        usuario_id: UUID,
        conversacion_id: UUID,
        texto: str,
        historial: Sequence[Mapping[str, str]] = (),
    ) -> dict[str, object] | None:
        """Resuelve el mensaje mediante una regla o herramienta disponible."""
