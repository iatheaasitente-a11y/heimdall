"""Interfaz común y respuesta estructurada de los motores LLM."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Mapping, Sequence


class ErrorRespuestaLLM(ValueError):
    """La respuesta del motor no tiene la estructura esperada."""


@dataclass(frozen=True)
class RespuestaEstructurada:
    """Intención detectada, argumentos de herramienta y confianza."""

    intencion: str
    campos: dict[str, object] = field(default_factory=dict)
    confianza: float = 0.0

    def __post_init__(self) -> None:
        """Valida que la respuesta represente una decisión estructurada.

        Raises:
            TypeError: Si la intención, los campos o la confianza tienen tipos inválidos.
            ValueError: Si la intención está vacía o la confianza sale de 0 a 1.
        """
        if not isinstance(self.intencion, str):
            raise TypeError("La intención debe ser texto.")
        if not self.intencion.strip():
            raise ValueError("La intención no puede estar vacía.")
        if not isinstance(self.campos, dict):
            raise TypeError("Los campos deben ser un diccionario.")
        if isinstance(self.confianza, bool) or not isinstance(
            self.confianza, (int, float)
        ):
            raise TypeError("La confianza debe ser un número.")
        if not 0 <= self.confianza <= 1:
            raise ValueError("La confianza debe estar entre 0 y 1.")


class MotorLLM(ABC):
    """Interfaz para motores que clasifican intención sin redactar respuestas."""

    @abstractmethod
    def interpretar(
        self,
        historial: Sequence[Mapping[str, str]],
        herramientas: Sequence[Mapping[str, object]],
    ) -> RespuestaEstructurada:
        """Interpreta el historial y devuelve solo intención, campos y confianza."""
