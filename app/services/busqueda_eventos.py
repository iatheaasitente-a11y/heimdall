"""Búsqueda de eventos por rango de fechas con filtros."""

from datetime import datetime
from uuid import UUID

from app.domain.schedule import EstadoEvento
from app.services.agenda import ServicioAgenda


class ServicioBusquedaEventos:
    """Busca eventos de un usuario en un rango de fechas con filtros opcionales.

    Envuelve un ``ServicioAgenda`` y añade un método que filtra los eventos por
    rango de fechas, título (búsqueda parcial) y estado.
    """

    def __init__(self, agenda: ServicioAgenda) -> None:
        """Crea el servicio sobre la agenda indicada."""
        self._agenda = agenda

    def buscar(
        self,
        usuario_id: UUID,
        desde: datetime,
        hasta: datetime,
        titulo: str | None = None,
        estado: EstadoEvento | None = None,
    ) -> list:
        """Busca eventos en un rango de fechas con filtros opcionales.

        Args:
            usuario_id: Identificador del usuario.
            desde: Inicio del rango (incluido).
            hasta: Fin del rango (incluido).
            titulo: Si se indica, filtra por título que contenga este texto.
            estado: Si se indica, filtra por estado del evento.

        Returns:
            Lista de eventos que cumplen los filtros, ordenados por inicio.
        """
        eventos = self._agenda.listar_eventos(usuario_id)
        resultados = [
            e
            for e in eventos
            if e.comienza >= desde and e.comienza <= hasta
        ]
        if titulo:
            resultados = [
                e for e in resultados if titulo.lower() in e.titulo.lower()
            ]
        if estado is not None:
            resultados = [e for e in resultados if e.estado == estado]
        resultados.sort(key=lambda e: e.comienza)
        return resultados
