"""Herramientas de usuario para programar y consultar recordatorios."""

from app.services.recordatorios import ServicioRecordatorios
from app.tools.base import Herramienta
from app.tools.esquemas import (
    Dia,
    IdentificadorRecordatorio,
    ListarRecordatorios,
    ProgramarRecordatorio,
)
from app.tools.resolucion import resolver_por_nombre


def herramientas_recordatorios(
    servicio: ServicioRecordatorios,
) -> list[Herramienta]:
    """Crea las herramientas de recordatorios que puede invocar el agente."""

    def recordatorio_id(usuario_id, argumentos):
        if argumentos["recordatorio_id"] is not None:
            return argumentos["recordatorio_id"]
        return resolver_por_nombre(
            argumentos["mensaje"],
            servicio.listar_recordatorios(usuario_id),
            lambda recordatorio: recordatorio.mensaje,
            "recordatorios",
        )

    return [
        Herramienta(
            "recordatorios_listar",
            "Lista todos los recordatorios del usuario.",
            ListarRecordatorios,
            lambda usuario_id, _args: servicio.listar_recordatorios(usuario_id),
        ),
        Herramienta(
            "recordatorios_programar",
            "Programa un recordatorio libre para una fecha futura.",
            ProgramarRecordatorio,
            lambda usuario_id, args: servicio.programar(usuario_id, **args),
        ),
        Herramienta(
            "recordatorios_cancelar",
            "Cancela un recordatorio pendiente.",
            IdentificadorRecordatorio,
            lambda usuario_id, args: servicio.cancelar(
                usuario_id, recordatorio_id(usuario_id, args)
            ),
        ),
        Herramienta(
            "recordatorios_pendientes_del_dia",
            "Lista los recordatorios pendientes de un día.",
            Dia,
            lambda usuario_id, args: servicio.pendientes_del_dia(
                usuario_id, args["dia"]
            ),
        ),
    ]
