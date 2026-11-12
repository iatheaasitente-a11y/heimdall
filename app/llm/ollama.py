"""Cliente mínimo de Ollama con salida estructurada y sin reintentos."""

import json
import math
import os
from collections.abc import Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from app.llm.interfaz import ErrorRespuestaLLM, MotorLLM, RespuestaEstructurada


class MotorOllama(MotorLLM):
    """Interpreta mensajes usando Ollama en la máquina local."""

    def __init__(
        self,
        url: str = "http://127.0.0.1:11434/api/chat",
        modelo: str | None = None,
        timeout: float | None = None,
    ) -> None:
        """Configura endpoint, modelo explícito y tiempo máximo por solicitud.

        Raises:
            ValueError: Si falta el modelo o un timeout no es positivo y finito.
        """
        if not isinstance(modelo, str) or not modelo.strip():
            raise ValueError("Se debe indicar explícitamente el nombre del modelo.")
        if timeout is None:
            try:
                timeout = float(os.getenv("HEIMDALL_LLM_TIMEOUT", "10"))
            except ValueError as error:
                raise ValueError(
                    "HEIMDALL_LLM_TIMEOUT debe ser un número positivo y finito."
                ) from error
        _validar_timeout(timeout)
        if not urlsplit(url).path.endswith("/api/chat"):
            raise ValueError("La URL de Ollama debe terminar en /api/chat.")
        self._url = url
        self._modelo = modelo.strip()
        self._timeout = timeout

    def calentar(self, timeout: float | None = None) -> None:
        """Carga el modelo con una solicitud mínima antes de iniciar el chat.

        Raises:
            OSError: Si Ollama no está disponible o falla la solicitud.
            ValueError: Si el timeout indicado no es positivo y finito.
        """
        limite = max(self._timeout, 30.0) if timeout is None else timeout
        _validar_timeout(limite)
        solicitud = Request(
            self._url,
            data=json.dumps(
                {
                    "model": self._modelo,
                    "messages": [{"role": "user", "content": ""}],
                    "stream": False,
                    "options": {"temperature": 0},
                    "keep_alive": "30m",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(solicitud, timeout=limite):
            pass

    def descargar(self, timeout: float, modelo: str | None = None) -> None:
        """Solicita descargar un modelo sin reintentos.

        Raises:
            OSError: Si Ollama no está disponible o falla la solicitud.
            ValueError: Si el timeout o el nombre del modelo no son válidos.
        """
        _validar_timeout(timeout)
        nombre = self._modelo if modelo is None else modelo
        if not isinstance(nombre, str) or not nombre.strip():
            raise ValueError("Se debe indicar explícitamente el nombre del modelo.")
        solicitud = Request(
            self._endpoint("generate"),
            data=json.dumps(
                {"model": nombre.strip(), "keep_alive": 0, "stream": False}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(solicitud, timeout=timeout) as response:
            response.read()

    def modelos_cargados(self, timeout: float) -> tuple[str, ...]:
        """Devuelve los nombres que Ollama informa como cargados.

        Raises:
            OSError: Si Ollama no está disponible o falla la solicitud.
            ErrorRespuestaLLM: Si la respuesta de ``/api/ps`` no es válida.
            ValueError: Si el timeout no es positivo y finito.
        """
        _validar_timeout(timeout)
        solicitud = Request(self._endpoint("ps"), method="GET")
        try:
            with urlopen(solicitud, timeout=timeout) as response:
                datos = json.loads(response.read().decode("utf-8"))
            modelos = datos["models"]
            if not isinstance(modelos, list):
                raise TypeError("models no es una lista")
            nombres = tuple(modelo["name"] for modelo in modelos)
            if any(not isinstance(nombre, str) or not nombre for nombre in nombres):
                raise TypeError("nombre de modelo inválido")
            return nombres
        except ErrorRespuestaLLM:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise ErrorRespuestaLLM(
                "Ollama devolvió una lista de modelos cargados inválida."
            ) from error

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
            "options": {"temperature": 0},
            "keep_alive": "30m",
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

    def _endpoint(self, recurso: str) -> str:
        """Construye otro endpoint de la misma instancia local de Ollama."""
        partes = urlsplit(self._url)
        base = partes.path.removesuffix("/api/chat")
        return urlunsplit(
            (partes.scheme, partes.netloc, f"{base}/api/{recurso}", partes.query, "")
        )


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


def _validar_timeout(timeout: float) -> None:
    """Rechaza límites de red inválidos."""
    try:
        valido = (
            not isinstance(timeout, bool)
            and isinstance(timeout, (int, float))
            and math.isfinite(timeout)
            and timeout > 0
        )
    except (OverflowError, TypeError, ValueError):
        valido = False
    if not valido:
        raise ValueError("El timeout debe ser un número positivo y finito.")
