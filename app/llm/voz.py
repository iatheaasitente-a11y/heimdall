"""Validación de audio WAV e interfaces para transcripción."""

import wave
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

AUDIO_MAX_BYTES = 20_000_000
AUDIO_MAX_DURACION = 300


class MotorVozNoDisponible(NotImplementedError):
    """Se solicitó transcripción, pero aún no hay un motor operativo."""


class ErrorAudio(ValueError):
    """El audio excede los límites o no es un WAV PCM válido."""


class MotorVoz(ABC):
    """Interfaz para convertir audio validado en texto."""

    @abstractmethod
    def transcribir(self, audio: Path) -> str:
        """Transcribe un archivo WAV.

        Raises:
            ErrorAudio: Si el archivo no cumple los límites.
            OSError: Si no se puede leer el archivo.
        """


class MotorVozFalso(MotorVoz):
    """Transcriptor determinista para pruebas sin red."""

    def __init__(self, transcripciones: Sequence[str]) -> None:
        """Configura los textos que devolverán las siguientes transcripciones."""
        self._transcripciones = list(transcripciones)
        self.audios: list[Path] = []

    def transcribir(self, audio: Path) -> str:
        """Valida el audio y devuelve el siguiente texto prefijado.

        Raises:
            ErrorAudio: Si el archivo no cumple los límites.
            OSError: Si no se puede leer el archivo.
            RuntimeError: Si no quedan transcripciones configuradas.
        """
        validar_audio(audio)
        self.audios.append(audio)
        if not self._transcripciones:
            raise RuntimeError("MotorVozFalso no tiene transcripciones configuradas.")
        return self._transcripciones.pop(0)


class MotorOllamaVoz(MotorVoz):
    """Esqueleto sin integración de red; no es un motor operativo."""

    def transcribir(self, audio: Path) -> str:
        """Valida el archivo y señala que la integración aún no está disponible.

        Raises:
            ErrorAudio: Si el archivo no cumple los límites.
            OSError: Si no se puede leer el archivo.
            MotorVozNoDisponible: La transcripción aún no está implementada.
        """
        validar_audio(audio)
        raise MotorVozNoDisponible("La transcripción con Ollama está pendiente.")


def validar_audio(ruta: Path) -> float:
    """Valida WAV PCM local y devuelve su duración en segundos.

    Raises:
        ErrorAudio: Si hay enlace simbólico, tamaño, duración o formato inválido.
        OSError: Si el archivo no se puede consultar o leer.
    """
    ruta = Path(ruta)
    if ruta.is_symlink():
        raise ErrorAudio("No se permiten enlaces simbólicos.")
    if ruta.stat().st_size > AUDIO_MAX_BYTES:
        raise ErrorAudio("El audio supera el máximo de 20 MB.")
    try:
        with wave.open(str(ruta), "rb") as archivo:
            if archivo.getcomptype() != "NONE":
                raise ErrorAudio("Solo se admite audio WAV PCM sin comprimir.")
            frecuencia = archivo.getframerate()
            fotogramas = archivo.getnframes()
    except (EOFError, wave.Error) as error:
        raise ErrorAudio("El archivo no es un WAV PCM válido.") from error
    if frecuencia <= 0 or fotogramas <= 0:
        raise ErrorAudio("El audio debe tener duración positiva.")
    duracion = fotogramas / frecuencia
    if duracion > AUDIO_MAX_DURACION:
        raise ErrorAudio("El audio supera los 300 segundos.")
    return duracion
