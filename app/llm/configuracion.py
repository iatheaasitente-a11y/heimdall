"""Selección explícita del motor mediante ``HEIMDALL_LLM``."""

import os
import time
from collections.abc import Mapping
from enum import StrEnum
from typing import Callable

from app.llm.interfaz import MotorLLM
from app.llm.nube import MotorNube
from app.llm.ollama import MotorOllama
from app.llm.planificador import PlanificadorModelos
from app.llm.roles import Catalogo, RolModelo


class ModoLLM(StrEnum):
    """Valores aceptados por la variable de entorno del motor."""

    APAGADO = "apagado"
    OLLAMA = "ollama"
    NUBE = "nube"


_VARIABLES_POR_ROL = {
    RolModelo.TEXTO: "HEIMDALL_MODELO_TEXTO",
    RolModelo.ENRUTADOR: "HEIMDALL_MODELO_ENRUTADOR",
    RolModelo.VISION: "HEIMDALL_MODELO_VISION",
    RolModelo.OCR: "HEIMDALL_MODELO_OCR",
    RolModelo.VOZ: "HEIMDALL_MODELO_VOZ",
}


def crear_catalogo(entorno: Mapping[str, str] | None = None) -> Catalogo:
    """Crea un catálogo desde variables explícitas, sin modificar el entorno.

    Los roles sin nombre de modelo quedan apagados.
    """
    variables = os.environ if entorno is None else entorno
    modelos = {
        rol: nombre.strip()
        for rol, variable in _VARIABLES_POR_ROL.items()
        if (nombre := variables.get(variable, "")).strip()
    }
    return Catalogo(modelos)


def crear_planificador(
    entorno: Mapping[str, str] | None = None,
    reloj: Callable[[], float] = time.monotonic,
) -> PlanificadorModelos:
    """Crea un planificador con los modelos y límites declarados por entorno."""
    return PlanificadorModelos(crear_catalogo(entorno), reloj=reloj)


def crear_motor(modo: str | None = None) -> MotorLLM | None:
    """Crea el motor configurado; por defecto devuelve ``None``.

    Raises:
        ValueError: Si el modo es inválido o Ollama no tiene modelo de texto.
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
        configuracion = crear_catalogo().obtener(RolModelo.TEXTO)
        if configuracion is None:
            raise ValueError(
                "HEIMDALL_LLM=ollama requiere HEIMDALL_MODELO_TEXTO."
            )
        return MotorOllama(modelo=configuracion.nombre)
    return MotorNube()
