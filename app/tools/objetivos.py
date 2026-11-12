"""Herramientas que delegan operaciones de objetivos en ``ServicioObjetivos``."""

from app.services.objetivos import ServicioObjetivos
from app.tools.base import Herramienta
from app.tools.esquemas import (
    ActualizarProgresoObjetivo,
    CambiarEstadoObjetivo,
    CrearObjetivo,
    ListarObjetivos,
)


def herramientas_objetivos(servicio: ServicioObjetivos) -> list[Herramienta]:
    """Crea las herramientas de objetivos disponibles para el agente."""
    return [
        Herramienta(
            "objetivos_crear",
            "Crea un objetivo personal.",
            CrearObjetivo,
            lambda usuario_id, args: servicio.crear_objetivo(usuario_id, **args),
        ),
        Herramienta(
            "objetivos_actualizar_progreso",
            "Actualiza el progreso de un objetivo activo.",
            ActualizarProgresoObjetivo,
            lambda usuario_id, args: servicio.actualizar_progreso(usuario_id, **args),
        ),
        Herramienta(
            "objetivos_pausar",
            "Pausa un objetivo activo.",
            CambiarEstadoObjetivo,
            lambda usuario_id, args: servicio.pausar_objetivo(
                usuario_id, args["objetivo_id"]
            ),
        ),
        Herramienta(
            "objetivos_reanudar",
            "Reanuda un objetivo pausado.",
            CambiarEstadoObjetivo,
            lambda usuario_id, args: servicio.reanudar_objetivo(
                usuario_id, args["objetivo_id"]
            ),
        ),
        Herramienta(
            "objetivos_cancelar",
            "Cancela un objetivo activo o pausado.",
            CambiarEstadoObjetivo,
            lambda usuario_id, args: servicio.cancelar_objetivo(
                usuario_id, args["objetivo_id"]
            ),
        ),
        Herramienta(
            "objetivos_listar",
            "Lista los objetivos, con un filtro opcional por estado.",
            ListarObjetivos,
            lambda usuario_id, args: servicio.listar_objetivos(usuario_id, **args),
        ),
    ]
