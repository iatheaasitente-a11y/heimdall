"""Límites de consultas y confianza para proteger el uso del motor."""

import logging
from collections.abc import Mapping, Sequence
from uuid import UUID

from app.llm.interfaz import ErrorRespuestaLLM, MotorLLM, RespuestaEstructurada
from app.llm.roles import confianza_suficiente


_LOG = logging.getLogger(__name__)


class FrenosLLM:
    """Limita consultas por conversación y descarta respuestas poco confiables."""

    def __init__(
        self,
        motor: MotorLLM,
        max_consultas: int = 3,
        confianza_minima: float = 0.70,
    ) -> None:
        """Crea los frenos con un máximo positivo y confianza entre cero y uno.

        Raises:
            ValueError: Si el máximo o el umbral no son válidos.
        """
        if max_consultas <= 0:
            raise ValueError("El máximo de consultas debe ser mayor que cero.")
        if not confianza_suficiente(confianza_minima, 0):
            raise ValueError("La confianza mínima debe estar entre 0 y 1.")
        self._motor = motor
        self._max_consultas = max_consultas
        self._confianza_minima = confianza_minima
        self._consultas: dict[UUID, int] = {}

    def consultar(
        self,
        conversacion_id: UUID,
        historial: Sequence[Mapping[str, str]],
        herramientas: Sequence[Mapping[str, object]],
    ) -> RespuestaEstructurada | None:
        """Interpreta si queda cuota y solo devuelve confianza suficiente.

        Una llamada que falla también consume una consulta; no se reintenta.
        """
        usadas = self._consultas.get(conversacion_id, 0)
        if usadas >= self._max_consultas:
            _LOG.warning("límite de consultas alcanzado.")
            return None
        self._consultas[conversacion_id] = usadas + 1
        try:
            respuesta = self._motor.interpretar(historial, herramientas)
        except OSError:
            _LOG.error("OSError al consultar el LLM.")
            return None
        except ErrorRespuestaLLM:
            _LOG.error("ErrorRespuestaLLM al interpretar la respuesta del LLM.")
            return None
        if not isinstance(respuesta, RespuestaEstructurada):
            _LOG.error("La respuesta no es RespuestaEstructurada.")
            return None
        confianza = respuesta.confianza
        if not confianza_suficiente(confianza, self._confianza_minima):
            _LOG.warning(
                "confianza insuficiente: %.2f < %.2f.",
                confianza,
                self._confianza_minima,
            )
            return None
        return respuesta
