"""Enrutamiento de los mensajes hacia el agente configurado."""

from collections.abc import Mapping, Sequence
from uuid import UUID

from app.agents.base import AgenteBase


class Router:
    """Delegador que ofrece una entrada estable al chatbot."""

    def __init__(self, agente: AgenteBase) -> None:
        """Asocia el agente que procesará los mensajes."""
        self._agente = agente

    def procesar(
        self,
        usuario_id: UUID,
        conversacion_id: UUID,
        texto: str,
        historial: Sequence[Mapping[str, str]] = (),
    ) -> dict[str, object] | None:
        """Entrega el mensaje al agente sin añadir lógica de negocio."""
        return self._agente.procesar(
            usuario_id,
            conversacion_id,
            texto,
            historial,
        )
