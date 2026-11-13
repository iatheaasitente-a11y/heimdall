"""Cancelación y reprogramación de eventos por título."""

from datetime import datetime
from uuid import UUID

from app.services.agenda import ServicioAgenda


class ServicioAgendaPorTitulo:
    """Operaciones de agenda que resuelven el evento por su título.

    Envuelve un ``ServicioAgenda`` y añade métodos que aceptan el título del
    evento en vez de su identificador, usando ``resolver_evento_id``.
    """

    def __init__(self, agenda: ServicioAgenda) -> None:
        """Crea el servicio sobre la agenda indicada."""
        self._agenda = agenda

    def cancelar_por_titulo(self, usuario_id: UUID, titulo: str) -> object:
        """Cancela el evento cuyo título coincide exactamente.

        Raises:
            EventoNoEncontrado: Si no hay ningún evento con ese título.
        """
        evento_id = self._agenda.resolver_evento_id(usuario_id, titulo)
        return self._agenda.cancelar_evento(usuario_id, evento_id)

    def reprogramar_por_titulo(
        self,
        usuario_id: UUID,
        titulo: str,
        comienza: datetime,
        termina: datetime,
    ) -> object:
        """Reprograma el evento cuyo título coincide exactamente.

        Raises:
            EventoNoEncontrado: Si no hay ningún evento con ese título.
            EventoNoActivo: Si el evento está cancelado o completado.
            ConflictoDeHorario: Si las nuevas horas se solapan con otro evento.
        """
        evento_id = self._agenda.resolver_evento_id(usuario_id, titulo)
        return self._agenda.reprogramar_evento(
            usuario_id, evento_id, comienza, termina
        )
