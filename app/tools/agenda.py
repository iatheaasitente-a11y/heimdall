"""Herramientas que delegan operaciones de agenda en ``ServicioAgenda``."""

from app.services.agenda import ServicioAgenda
from app.tools.base import Herramienta
from app.tools.esquemas import CrearEvento, Dia, IdentificadorEvento, ReprogramarEvento
from app.tools.resolucion import resolver_por_nombre


def herramientas_agenda(servicio: ServicioAgenda) -> list[Herramienta]:
    """Crea las herramientas de agenda disponibles para el agente."""

    def evento_id(usuario_id, argumentos):
        if argumentos["evento_id"] is not None:
            return argumentos["evento_id"]
        return resolver_por_nombre(
            argumentos["titulo"],
            servicio.listar_eventos(usuario_id),
            lambda evento: evento.titulo,
            "eventos",
        )

    def cambiar_estado(usuario_id, argumentos, metodo):
        return metodo(usuario_id, evento_id(usuario_id, argumentos))

    def reprogramar(usuario_id, argumentos):
        return servicio.reprogramar_evento(
            usuario_id,
            evento_id(usuario_id, argumentos),
            argumentos["comienza"],
            argumentos["termina"],
        )

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
            lambda usuario_id, args: cambiar_estado(
                usuario_id, args, servicio.cancelar_evento
            ),
        ),
        Herramienta(
            "agenda_completar_evento",
            "Marca un evento como completado.",
            IdentificadorEvento,
            lambda usuario_id, args: cambiar_estado(
                usuario_id, args, servicio.completar_evento
            ),
        ),
        Herramienta(
            "agenda_reprogramar_evento",
            "Cambia el inicio y fin de un evento activo.",
            ReprogramarEvento,
            reprogramar,
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
