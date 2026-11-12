"""Avisos previos configurables para eventos de la agenda."""

from datetime import timedelta
from uuid import UUID

from app.services.recordatorios import ServicioRecordatorios


class ServicioAvisosPrevios:
    """Programa avisos X minutos antes del inicio de un evento.

    Envuelve un ``ServicioRecordatorios`` y añade un método que calcula la hora
    del aviso restando los minutos indicados al inicio del evento.
    """

    def __init__(self, recordatorios: ServicioRecordatorios) -> None:
        """Crea el servicio sobre el servicio de recordatorios indicado."""
        self._recordatorios = recordatorios

    def programar_aviso_previo(
        self,
        usuario_id: UUID,
        evento_id: UUID,
        minutos_antes: int,
    ) -> object:
        """Programa un aviso X minutos antes del inicio de un evento.

        Args:
            usuario_id: Identificador del usuario.
            evento_id: Identificador del evento.
            minutos_antes: Minutos antes del inicio en los que avisar.

        Returns:
            El recordatorio creado.
        """
        return self._recordatorios.programar_para_evento(
            usuario_id, evento_id, timedelta(minutes=minutos_antes)
        )
