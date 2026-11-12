"""Herramientas que delegan operaciones de agenda en ``ServicioAgenda``."""

from app.services.agenda import ServicioAgenda
from app.tools.base import Herramienta
from app.tools.esquemas import CrearEvento, Dia, IdentificadorEvento, ReprogramarEvento


def herramientas_agenda(servicio: ServicioAgenda) -> list[Herramienta]:
    """Crea las herramientas de agenda disponibles para el agente."""
    return [
        Herramienta(
            "agenda_crear_evento",
            "Crea un evento en la agenda.",
            CrearEvento,
            lambda usuario_id, args: servicio.crear_evento(usuario_id, **args),
        ),
        Herramienta(
            "agenda_cancelar_evento",
            "Cancela un evento de la agenda.",
            IdentificadorEvento,
            lambda usuario_id, args: servicio.cancelar_evento(
                usuario_id, args["evento_id"]
            ),
        ),
        Herramienta(
            "agenda_completar_evento",
            "Marca un evento como completado.",
            IdentificadorEvento,
            lambda usuario_id, args: servicio.completar_evento(
                usuario_id, args["evento_id"]
            ),
        ),
        Herramienta(
            "agenda_reprogramar_evento",
            "Cambia el inicio y fin de un evento activo.",
            ReprogramarEvento,
            lambda usuario_id, args: servicio.reprogramar_evento(usuario_id, **args),
        ),
        Herramienta(
            "agenda_eventos_del_dia",
            "Lista los eventos activos de un día.",
            Dia,
            lambda usuario_id, args: servicio.eventos_del_dia(
                usuario_id, args["dia"]
            ),
        ),
    ]
