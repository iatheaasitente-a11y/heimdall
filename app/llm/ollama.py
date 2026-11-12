"""Cliente mínimo de Ollama con salida estructurada y sin reintentos."""

import json
from collections.abc import Mapping, Sequence
from urllib.request import Request, urlopen

from app.llm.interfaz import ErrorRespuestaLLM, MotorLLM, RespuestaEstructurada


class MotorOllama(MotorLLM):
    """Interpreta mensajes usando Ollama en la máquina local."""

    def __init__(
        self,
        url: str = "http://127.0.0.1:11434/api/chat",
        modelo: str = "llama3.2:3b",
        timeout: float = 10.0,
    ) -> None:
        """Configura endpoint, modelo local y tiempo máximo por solicitud."""
        if timeout <= 0:
            raise ValueError("El timeout debe ser mayor que cero.")
        self._url = url
        self._modelo = modelo
        self._timeout = timeout

    def interpretar(
        self,
        historial: Sequence[Mapping[str, str]],
        herramientas: Sequence[Mapping[str, object]],
    ) -> RespuestaEstructurada:
        """Envía una solicitud estructurada a Ollama, sin reintentar.

        Raises:
            OSError: Si Ollama no está disponible o falla la solicitud.
            ErrorRespuestaLLM: Si el motor no devuelve el formato solicitado.
        """
        instrucciones = (
            "Clasifica la intención del usuario y devuelve solo JSON con "
            "intencion, campos y confianza. No redactes una respuesta final ni "
            "inventes cifras o fechas. Las herramientas disponibles y sus "
            "esquemas son: "
            + json.dumps(list(herramientas), ensure_ascii=False)
        )
        mensajes = [{"role": "system", "content": instrucciones}]
        mensajes.extend(
            {"role": mensaje["role"], "content": mensaje["content"]}
            for mensaje in historial
        )
        solicitud = {
            "model": self._modelo,
            "messages": mensajes,
            "stream": False,
            "format": _ESQUEMA_RESPUESTA,
        }
        request = Request(
            self._url,
            data=json.dumps(solicitud, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                cuerpo = json.loads(response.read().decode("utf-8"))
            contenido = cuerpo["message"]["content"]
            datos = json.loads(contenido)
            if not isinstance(datos, dict) or set(datos) != {
                "intencion",
                "campos",
                "confianza",
            }:
                raise ErrorRespuestaLLM("La respuesta no cumple el esquema esperado.")
            return RespuestaEstructurada(**datos)
        except ErrorRespuestaLLM:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise ErrorRespuestaLLM("Ollama devolvió una respuesta inválida.") from error


_ESQUEMA_RESPUESTA = {
    "type": "object",
    "properties": {
        "intencion": {"type": "string"},
        "campos": {"type": "object"},
        "confianza": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["intencion", "campos", "confianza"],
    "additionalProperties": False,
}
