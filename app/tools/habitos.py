"""Herramientas que delegan operaciones de hábitos en ``ServicioHabitos``."""

from app.services.habitos import ServicioHabitos
from app.tools.base import Herramienta
from app.tools.esquemas import ConsultarHabito, CrearHabito, RegistrarProgresoHabito


def herramientas_habitos(servicio: ServicioHabitos) -> list[Herramienta]:
    """Crea las herramientas de hábitos disponibles para el agente."""
    return [
        Herramienta(
            "habitos_crear",
            "Crea un hábito para el usuario.",
            CrearHabito,
            lambda usuario_id, args: servicio.crear_habito(usuario_id, **args),
        ),
        Herramienta(
            "habitos_registrar_progreso",
            "Añade progreso a un hábito.",
            RegistrarProgresoHabito,
            lambda usuario_id, args: servicio.registrar_progreso(
                usuario_id, **args
            ),
        ),
        Herramienta(
            "habitos_progreso_del_dia",
            "Consulta el progreso de un hábito en un día.",
            ConsultarHabito,
            lambda usuario_id, args: servicio.progreso_del_dia(usuario_id, **args),
        ),
        Herramienta(
            "habitos_racha",
            "Consulta la racha de un hábito diario.",
            ConsultarHabito,
            lambda usuario_id, args: servicio.racha(
                usuario_id, args["habito_id"], hoy=args["dia"]
            ),
        ),
    ]
