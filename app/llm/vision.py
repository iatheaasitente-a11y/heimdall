"""Validación de imágenes y motores de visión/OCR."""

import base64
import json
import struct
import zlib
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
from urllib.request import Request, urlopen

from app.llm.interfaz import ErrorRespuestaLLM, RespuestaEstructurada
from app.llm.ollama import MotorOllama

IMAGEN_MAX_BYTES = 5_000_000
IMAGEN_MAX_LADO = 4096


class ErrorImagen(ValueError):
    """La imagen está fuera de los límites o no es JPEG/PNG válido."""


class MotorVision(ABC):
    """Interfaz para interpretar una imagen sin producir respuesta final."""

    @abstractmethod
    def interpretar_imagen(
        self,
        imagen: Path | bytes,
        instruccion: str,
    ) -> RespuestaEstructurada:
        """Interpreta una imagen validada.

        Raises:
            ErrorImagen: Si el archivo no cumple los límites.
            OSError: Si no se puede leer una ruta local.
        """


class MotorVisionFalso(MotorVision):
    """Motor determinista para pruebas de visión y OCR."""

    def __init__(self, respuestas: Sequence[RespuestaEstructurada]) -> None:
        """Configura respuestas estructuradas prefijadas."""
        self._respuestas = list(respuestas)
        self.imagenes: list[Path | bytes] = []
        self.instrucciones: list[str] = []

    def interpretar_imagen(
        self,
        imagen: Path | bytes,
        instruccion: str,
    ) -> RespuestaEstructurada:
        """Devuelve la siguiente respuesta prefijada.

        Raises:
            ErrorImagen: Si el archivo no cumple los límites.
            RuntimeError: Si no quedan respuestas configuradas.
        """
        validar_imagen(imagen)
        self.imagenes.append(imagen)
        self.instrucciones.append(instruccion)
        if not self._respuestas:
            raise RuntimeError("MotorVisionFalso no tiene respuestas configuradas.")
        return self._respuestas.pop(0)


class MotorOllamaVision(MotorOllama, MotorVision):
    """Envía imágenes a Ollama con salida estructurada y sin reintentos."""

    def interpretar_imagen(
        self,
        imagen: Path | bytes,
        instruccion: str,
    ) -> RespuestaEstructurada:
        """Interpreta JPEG/PNG local con el modelo configurado.

        Raises:
            ErrorImagen: Si el archivo no cumple los límites.
            OSError: Si Ollama no está disponible.
            ErrorRespuestaLLM: Si la salida estructurada es inválida.
        """
        contenido = validar_imagen(imagen)
        solicitud = {
            "model": self._modelo,
            "messages": [
                {
                    "role": "user",
                    "content": instruccion,
                    "images": [base64.b64encode(contenido).decode("ascii")],
                }
            ],
            "stream": False,
            "format": {
                "type": "object",
                "properties": {
                    "intencion": {"type": "string"},
                    "campos": {"type": "object"},
                    "confianza": {"type": "number"},
                },
                "required": ["intencion", "campos", "confianza"],
                "additionalProperties": False,
            },
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
            datos = json.loads(cuerpo["message"]["content"])
            if not isinstance(datos, dict) or set(datos) != {
                "intencion",
                "campos",
                "confianza",
            }:
                raise ErrorRespuestaLLM("La salida de visión no cumple el esquema.")
            return RespuestaEstructurada(**datos)
        except ErrorRespuestaLLM:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise ErrorRespuestaLLM("Ollama devolvió una salida de visión inválida.") from error


def validar_imagen(ruta: Path | bytes) -> bytes:
    """Obtiene y valida una imagen JPEG/PNG desde una ruta o bytes.

    Raises:
        ErrorImagen: Si hay enlace simbólico, tamaño, formato o dimensiones inválidos.
        OSError: Si una ruta local no se puede consultar o leer.
    """
    if isinstance(ruta, bytes):
        contenido = ruta
    else:
        ruta = Path(ruta)
        if ruta.is_symlink():
            raise ErrorImagen("No se permiten enlaces simbólicos.")
        if ruta.stat().st_size > IMAGEN_MAX_BYTES:
            raise ErrorImagen("La imagen supera el máximo de 5 MB.")
        contenido = ruta.read_bytes()
    if not contenido:
        raise ErrorImagen("La imagen está vacía.")
    if len(contenido) > IMAGEN_MAX_BYTES:
        raise ErrorImagen("La imagen supera el máximo de 5 MB.")
    dimensiones = _dimensiones_png(contenido)
    if dimensiones is None:
        dimensiones = _dimensiones_jpeg(contenido)
    if dimensiones is None:
        raise ErrorImagen("Solo se admiten imágenes JPEG o PNG válidas.")
    ancho, alto = dimensiones
    if ancho <= 0 or alto <= 0:
        raise ErrorImagen("La imagen tiene dimensiones inválidas.")
    if ancho > IMAGEN_MAX_LADO or alto > IMAGEN_MAX_LADO:
        raise ErrorImagen("La imagen supera los 4096 píxeles por lado.")
    return contenido


def _dimensiones_png(contenido: bytes) -> tuple[int, int] | None:
    if not contenido.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    if len(contenido) < 33 or int.from_bytes(contenido[8:12], "big") != 13:
        raise ErrorImagen("El encabezado PNG está incompleto.")
    if contenido[12:16] != b"IHDR":
        raise ErrorImagen("El encabezado PNG no empieza con IHDR.")
    dimensiones = struct.unpack(">II", contenido[16:24])
    if zlib.crc32(contenido[12:29]) & 0xFFFFFFFF != int.from_bytes(
        contenido[29:33], "big"
    ):
        raise ErrorImagen("La suma de comprobación del encabezado PNG no es válida.")
    posicion = 33
    hay_datos = False
    while posicion + 12 <= len(contenido):
        longitud = int.from_bytes(contenido[posicion : posicion + 4], "big")
        fin = posicion + 12 + longitud
        if fin > len(contenido):
            break
        tipo = contenido[posicion + 4 : posicion + 8]
        datos = contenido[posicion + 8 : posicion + 8 + longitud]
        crc = int.from_bytes(contenido[posicion + 8 + longitud : fin], "big")
        if zlib.crc32(tipo + datos) & 0xFFFFFFFF != crc:
            raise ErrorImagen("La suma de comprobación PNG no es válida.")
        if tipo == b"IDAT":
            hay_datos = True
        elif tipo == b"IEND":
            if longitud != 0 or not hay_datos or fin != len(contenido):
                raise ErrorImagen("El contenido PNG está incompleto.")
            return dimensiones
        posicion = fin
    raise ErrorImagen("El contenido PNG está incompleto.")


def _dimensiones_jpeg(contenido: bytes) -> tuple[int, int] | None:
    if not contenido.startswith(b"\xff\xd8"):
        return None
    marcadores_sof = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    posicion = 2
    while posicion < len(contenido):
        while posicion < len(contenido) and contenido[posicion] != 0xFF:
            posicion += 1
        while posicion < len(contenido) and contenido[posicion] == 0xFF:
            posicion += 1
        if posicion >= len(contenido):
            break
        marcador = contenido[posicion]
        posicion += 1
        if marcador in {0xD8, 0xD9} or 0xD0 <= marcador <= 0xD7:
            continue
        if posicion + 2 > len(contenido):
            break
        longitud = int.from_bytes(contenido[posicion : posicion + 2], "big")
        if longitud < 2 or posicion + longitud > len(contenido):
            break
        if marcador in marcadores_sof:
            if longitud < 7:
                break
            alto, ancho = struct.unpack(">HH", contenido[posicion + 3 : posicion + 7])
            if b"\xff\xd9" not in contenido[posicion + longitud :]:
                raise ErrorImagen("El contenido JPEG está incompleto.")
            return ancho, alto
        posicion += longitud
        if marcador == 0xDA:
            break
    raise ErrorImagen("El encabezado JPEG no contiene dimensiones válidas.")
