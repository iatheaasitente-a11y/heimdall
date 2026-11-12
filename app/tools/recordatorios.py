"""Herramientas de usuario para programar y consultar recordatorios."""

from app.services.recordatorios import ServicioRecordatorios
from app.tools.base import Herramienta
from app.tools.esquemas import (
    Dia,
    IdentificadorRecordatorio,
    ProgramarRecordatorio,
)


def herramientas_recordatorios(
    servicio: ServicioRecordatorios,
) -> list[Herramienta]:
    """Crea las herramientas de recordatorios que puede invocar el agente."""
    return [
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
                usuario_id, args["recordatorio_id"]
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
