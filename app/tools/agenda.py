"""Herramientas que delegan operaciones de agenda en ``ServicioAgenda``."""

from app.services.agenda import ServicioAgenda
from app.tools.base import Herramienta
from app.tools.esquemas import (
    ConsultaHuecos,
    CrearEvento,
    Dia,
    IdentificadorEvento,
    Momento,
    ReprogramarEvento,
)


def herramientas_agenda(servicio: ServicioAgenda) -> list[Herramienta]:
    """Crea las herramientas de agenda disponibles para el agente."""

    def evento_id(usuario_id, argumentos):
        if argumentos["evento_id"] is not None:
            return argumentos["evento_id"]
        return servicio.resolver_evento_id(usuario_id, argumentos["titulo"])

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
            "agenda_proximo_evento",
            "Devuelve el siguiente evento activo de la agenda.",
            Momento,
            lambda usuario_id, args: servicio.proximo_evento(
                usuario_id,
                args["ahora"],
            ),
        ),
        Herramienta(
            "agenda_huecos_libres",
            "Devuelve los huecos libres de una franja.",
            ConsultaHuecos,
            lambda usuario_id, args: servicio.huecos_libres(
                usuario_id,
                args["dia"],
                args["desde"],
                args["hasta"],
                args["minutos"],
            ),
        ),
        Herramienta(
            "agenda_consultar_evento",
            "Devuelve los datos de un evento por identificador o titulo.",
            IdentificadorEvento,
            lambda usuario_id, args: servicio.obtener_evento(
                usuario_id,
                evento_id(usuario_id, args),
            ),
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
