"""Motor determinista para pruebas, sin acceso a red ni a modelos."""

from collections.abc import Mapping, Sequence

from app.llm.interfaz import MotorLLM, RespuestaEstructurada


class MotorFalso(MotorLLM):
    """Devuelve respuestas prefijadas y conserva la última solicitud recibida."""

    def __init__(
        self, respuestas: Sequence[RespuestaEstructurada] | None = None
    ) -> None:
        """Crea el motor con las respuestas que devolverá en orden."""
        self._respuestas = list(respuestas or [])
        self._indice = 0
        self.ultimo_historial: list[dict[str, str]] = []
        self.ultimas_herramientas: list[dict[str, object]] = []

    def interpretar(
        self,
        historial: Sequence[Mapping[str, str]],
        herramientas: Sequence[Mapping[str, object]],
    ) -> RespuestaEstructurada:
        """Devuelve la siguiente respuesta prefijada.

        Raises:
            RuntimeError: Si no quedan respuestas configuradas.
        """
        self.ultimo_historial = [dict(mensaje) for mensaje in historial]
        self.ultimas_herramientas = [dict(herramienta) for herramienta in herramientas]
        if self._indice >= len(self._respuestas):
            raise RuntimeError("MotorFalso no tiene más respuestas configuradas.")
        respuesta = self._respuestas[self._indice]
        self._indice += 1
        return respuesta
