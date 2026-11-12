"""Creación de agentes según el tipo y el motor configurados."""

from collections.abc import Callable
from datetime import date
from uuid import UUID

from app.agents.base import AgenteBase
from app.agents.personal import AgentePersonal
from app.llm.configuracion import crear_motor
from app.llm.interfaz import MotorLLM
from app.tools.registro import RegistroHerramientas


def crear_agente(
    tipo: str,
    herramientas: RegistroHerramientas,
    hoy_por_usuario: Callable[[UUID], date],
    motor: MotorLLM | None = None,
    modo_llm: str | None = None,
) -> AgenteBase:
    """Crea un agente soportado y configura el motor LLM.

    Raises:
        ValueError: Si ``tipo`` no identifica un agente disponible.
    """
    if tipo != "personal":
        raise ValueError(f"No existe el agente «{tipo}».")
    motor_seleccionado = motor if motor is not None else crear_motor(modo_llm)
    return AgentePersonal(herramientas, motor_seleccionado, hoy_por_usuario)
