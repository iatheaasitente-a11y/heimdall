"""Selección explícita del motor mediante ``HEIMDALL_LLM``."""

import os
from enum import StrEnum

from app.llm.interfaz import MotorLLM
from app.llm.nube import MotorNube
from app.llm.ollama import MotorOllama


class ModoLLM(StrEnum):
    """Valores aceptados por la variable de entorno del motor."""

    APAGADO = "apagado"
    OLLAMA = "ollama"
    NUBE = "nube"


def crear_motor(modo: str | None = None) -> MotorLLM | None:
    """Crea el motor configurado; por defecto devuelve ``None``.

    Raises:
        ValueError: Si el modo no es ``apagado``, ``ollama`` o ``nube``.
    """
    configurado = modo if modo is not None else os.getenv("HEIMDALL_LLM", "apagado")
    try:
        seleccionado = ModoLLM(configurado)
    except ValueError as error:
        opciones = ", ".join(modo.value for modo in ModoLLM)
        raise ValueError(f"HEIMDALL_LLM debe ser uno de: {opciones}.") from error
    if seleccionado == ModoLLM.APAGADO:
        return None
    if seleccionado == ModoLLM.OLLAMA:
        return MotorOllama()
    return MotorNube()
