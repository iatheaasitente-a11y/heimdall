"""Herramientas que delegan operaciones de objetivos en ``ServicioObjetivos``."""

from app.services.objetivos import ServicioObjetivos
from app.tools.base import Herramienta
from app.tools.esquemas import (
    ActualizarProgresoObjetivo,
    CambiarEstadoObjetivo,
    CrearObjetivo,
    ListarObjetivos,
)
from app.tools.resolucion import resolver_por_nombre


def herramientas_objetivos(servicio: ServicioObjetivos) -> list[Herramienta]:
    """Crea las herramientas de objetivos disponibles para el agente."""

    def objetivo_id(usuario_id, argumentos):
        if argumentos["objetivo_id"] is not None:
            return argumentos["objetivo_id"]
        return resolver_por_nombre(
            argumentos["nombre"],
            servicio.listar_objetivos(usuario_id),
            lambda objetivo: objetivo.nombre,
            "objetivos",
        )

    def actualizar(usuario_id, argumentos):
        return servicio.actualizar_progreso(
            usuario_id,
            objetivo_id(usuario_id, argumentos),
            argumentos["progreso"],
        )

    def cambiar_estado(usuario_id, argumentos, metodo):
        return metodo(usuario_id, objetivo_id(usuario_id, argumentos))

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
            actualizar,
        ),
        Herramienta(
            "objetivos_pausar",
            "Pausa un objetivo activo.",
            CambiarEstadoObjetivo,
            lambda usuario_id, args: cambiar_estado(
                usuario_id, args, servicio.pausar_objetivo
            ),
        ),
        Herramienta(
            "objetivos_reanudar",
            "Reanuda un objetivo pausado.",
            CambiarEstadoObjetivo,
            lambda usuario_id, args: cambiar_estado(
                usuario_id, args, servicio.reanudar_objetivo
            ),
        ),
        Herramienta(
            "objetivos_cancelar",
            "Cancela un objetivo activo o pausado.",
            CambiarEstadoObjetivo,
            lambda usuario_id, args: cambiar_estado(
                usuario_id, args, servicio.cancelar_objetivo
            ),
        ),
        Herramienta(
            "objetivos_listar",
            "Lista los objetivos, con un filtro opcional por estado.",
            ListarObjetivos,
            lambda usuario_id, args: servicio.listar_objetivos(usuario_id, **args),
        ),
    ]
