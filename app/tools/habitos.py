"""Herramientas que delegan operaciones de hábitos en ``ServicioHabitos``."""

from app.services.habitos import ServicioHabitos
from app.tools.base import Herramienta
from app.tools.esquemas import (
    ConsultarHabito,
    CrearHabito,
    ListarHabitos,
    RegistrarProgresoHabito,
)
from app.tools.resolucion import resolver_por_nombre


def herramientas_habitos(servicio: ServicioHabitos) -> list[Herramienta]:
    """Crea las herramientas de hábitos disponibles para el agente."""

    def habito_id(usuario_id, argumentos):
        if argumentos["habito_id"] is not None:
            return argumentos["habito_id"]
        return resolver_por_nombre(
            argumentos["nombre"],
            servicio.listar_habitos(usuario_id),
            lambda habito: habito.nombre,
            "hábitos",
        )

    def registrar(usuario_id, argumentos):
        return servicio.registrar_progreso(
            usuario_id,
            habito_id(usuario_id, argumentos),
            argumentos["valor"],
            cuando=argumentos["cuando"],
            notas=argumentos["notas"],
        )

    def progreso(usuario_id, argumentos):
        return servicio.progreso_del_dia(
            usuario_id,
            habito_id(usuario_id, argumentos),
            dia=argumentos["dia"],
        )

    def racha(usuario_id, argumentos):
        return servicio.racha(
            usuario_id,
            habito_id(usuario_id, argumentos),
            hoy=argumentos["dia"],
        )

    return [
        Herramienta(
            "habitos_listar",
            "Lista los hábitos del usuario, incluidos los inactivos.",
            ListarHabitos,
            lambda usuario_id, args: servicio.listar_habitos(usuario_id, **args),
        ),
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
            registrar,
        ),
        Herramienta(
            "habitos_progreso_del_dia",
            "Consulta el progreso de un hábito en un día.",
            ConsultarHabito,
            progreso,
        ),
        Herramienta(
            "habitos_racha",
            "Consulta la racha de un hábito diario.",
            ConsultarHabito,
            racha,
        ),
    ]
