"""Herramientas de usuario para programar y consultar recordatorios."""

from datetime import timedelta

from app.services.recordatorios import ServicioRecordatorios
from app.tools.base import Herramienta
from app.tools.esquemas import (
    Dia,
    IdentificadorRecordatorio,
    ListarRecordatorios,
    ProgramarRecordatorio,
    RecordatorioDeEvento,
)


def herramientas_recordatorios(
    servicio: ServicioRecordatorios,
) -> list[Herramienta]:
    """Crea las herramientas de recordatorios que puede invocar el agente."""

    def recordatorio_id(usuario_id, argumentos):
        if argumentos["recordatorio_id"] is not None:
            return argumentos["recordatorio_id"]
        return servicio.resolver_recordatorio_id(
            usuario_id,
            argumentos["mensaje"],
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
            "recordatorios_programar_para_evento",
            "Programa un aviso antes de un evento.",
            RecordatorioDeEvento,
            lambda usuario_id, args: servicio.programar_para_evento(
                usuario_id,
                servicio.resolver_evento_id(
                    usuario_id,
                    args["titulo"],
                )
                if args["evento_id"] is None
                else args["evento_id"],
                timedelta(minutes=args["minutos"]),
            ),
        ),
        Herramienta(
            "recordatorios_cancelar",
            "Cancela un recordatorio pendiente.",
            IdentificadorRecordatorio,
            lambda usuario_id, args: servicio.cancelar(
                usuario_id,
                recordatorio_id(usuario_id, args),
            ),
        ),
        Herramienta(
            "recordatorios_pendientes_del_dia",
            "Lista los recordatorios pendientes de un día.",
            Dia,
            lambda usuario_id, args: servicio.pendientes_del_dia(
                usuario_id,
                args["dia"],
            ),
        ),
    ]
