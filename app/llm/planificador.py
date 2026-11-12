"""Planificación secuencial de modelos Ollama por rol."""

import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from threading import Lock
from typing import Protocol

from app.llm.interfaz import ErrorRespuestaLLM, RespuestaEstructurada
from app.llm.ollama import MotorOllama
from app.llm.roles import (
    Catalogo,
    ModeloConfigurado,
    RolModelo,
    confianza_suficiente,
    normalizar_nombre_modelo,
)
from app.llm.vision import ErrorImagen, MotorOllamaVision, validar_imagen
from app.llm.voz import MotorVozNoDisponible


class _MotorGestionable(Protocol):
    """Operaciones que el planificador necesita de un motor local."""

    def calentar(self, timeout: float | None = None) -> None: ...

    def descargar(self, timeout: float, modelo: str | None = None) -> None: ...

    def modelos_cargados(self, timeout: float) -> tuple[str, ...]: ...

    def interpretar(
        self,
        historial: Sequence[Mapping[str, str]],
        herramientas: Sequence[Mapping[str, object]],
    ) -> RespuestaEstructurada: ...


class _Cerrojo(Protocol):
    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool: ...

    def release(self) -> None: ...


_CERROJO_PROCESO = Lock()


class PlanificadorModelos:
    """Serializa las cargas y exige comprobar la descarga antes de cambiar."""

    def __init__(
        self,
        catalogo: Catalogo,
        fabrica_motor: Callable[[ModeloConfigurado], _MotorGestionable] | None = None,
        reloj: Callable[[], float] = time.monotonic,
        cerrojo: _Cerrojo | None = None,
    ) -> None:
        """Inyecta el catálogo, la fábrica, el reloj monotónico y el lock.

        El lock por defecto es compartido por los planificadores de este proceso.
        """
        self._catalogo = catalogo
        self._fabrica_motor = fabrica_motor or _crear_motor
        self._reloj = reloj
        self._cerrojo = _CERROJO_PROCESO if cerrojo is None else cerrojo

    def interpretar(
        self,
        rol: RolModelo,
        historial: Sequence[Mapping[str, str]],
        herramientas: Sequence[Mapping[str, object]],
    ) -> RespuestaEstructurada | None:
        """Interpreta con el rol configurado o devuelve ``None`` si está apagado.

        Raises:
            TimeoutError: Si no se obtiene el lock o se excede un plazo.
            OSError: Si falla la comunicación local con Ollama.
            ErrorRespuestaLLM: Si no se puede verificar la carga o la descarga.
            TypeError: Si el rol no es un ``RolModelo``.
        """
        configuracion = self._catalogo.obtener(rol)
        if configuracion is None:
            return None
        politica = configuracion.politica
        if not self._cerrojo.acquire(timeout=politica.bloqueo):
            raise TimeoutError(f"Se agotó la espera del planificador para {rol.value}.")
        try:
            motor = self._fabrica_motor(configuracion)
            self._preparar_modelo(motor, configuracion)
            respuesta = self._inferir(
                motor,
                configuracion,
                historial,
                herramientas,
            )
            if not isinstance(respuesta, RespuestaEstructurada):
                return None
            if not confianza_suficiente(
                getattr(respuesta, "confianza", None),
                politica.confianza_minima,
            ):
                return None
            return respuesta
        finally:
            self._cerrojo.release()

    def interpretar_imagen(
        self,
        rol: RolModelo,
        imagen: Path,
        instruccion: str,
    ) -> RespuestaEstructurada | None:
        """Interpreta una imagen mediante el rol VISION u OCR configurado.

        Raises:
            ValueError: Si se usa un rol distinto de VISION u OCR.
            ErrorImagen: Si la imagen excede los límites o no es JPEG/PNG válido.
            TimeoutError: Si no se obtiene el lock o se excede un plazo.
            OSError: Si no se puede leer la imagen o falla Ollama.
            ErrorRespuestaLLM: Si no se puede verificar la carga del modelo.
        """
        if rol not in {RolModelo.VISION, RolModelo.OCR}:
            raise ValueError("Las imágenes requieren el rol VISION u OCR.")
        configuracion = self._catalogo.obtener(rol)
        if configuracion is None:
            return None
        validar_imagen(imagen)
        politica = configuracion.politica
        if not self._cerrojo.acquire(timeout=politica.bloqueo):
            raise TimeoutError(f"Se agotó la espera del planificador para {rol.value}.")
        try:
            motor = self._fabrica_motor(configuracion)
            self._preparar_modelo(motor, configuracion)
            interpretar_imagen = getattr(motor, "interpretar_imagen", None)
            if not callable(interpretar_imagen):
                raise TypeError("El motor configurado no admite entradas de imagen.")
            inicio = self._reloj()
            respuesta = interpretar_imagen(imagen, instruccion)
            self._comprobar_plazo(inicio, politica.inferencia, "inferencia")
            if not isinstance(respuesta, RespuestaEstructurada):
                return None
            if not confianza_suficiente(
                getattr(respuesta, "confianza", None),
                politica.confianza_minima,
            ):
                return None
            return respuesta
        finally:
            self._cerrojo.release()

    def _preparar_modelo(
        self,
        motor: _MotorGestionable,
        configuracion: ModeloConfigurado,
    ) -> None:
        """Descarga modelos distintos y comprueba la carga del modelo elegido."""
        politica = configuracion.politica
        inicio_descarga = self._reloj()
        cargados = motor.modelos_cargados(timeout=politica.descarga)
        self._comprobar_plazo(inicio_descarga, politica.descarga, "descarga")
        while True:
            anterior = next(
                (
                    nombre
                    for nombre in cargados
                    if normalizar_nombre_modelo(nombre) != configuracion.nombre
                ),
                None,
            )
            if anterior is None:
                break
            restante = self._restante(inicio_descarga, politica.descarga, "descarga")
            motor.descargar(timeout=restante, modelo=anterior)
            restante = self._restante(inicio_descarga, politica.descarga, "descarga")
            cargados = motor.modelos_cargados(timeout=restante)
            self._comprobar_plazo(inicio_descarga, politica.descarga, "descarga")
            if any(
                normalizar_nombre_modelo(nombre)
                == normalizar_nombre_modelo(anterior)
                for nombre in cargados
            ):
                raise ErrorRespuestaLLM(
                    f"No se pudo confirmar la descarga del modelo {anterior}."
                )

        if any(
            normalizar_nombre_modelo(nombre) == configuracion.nombre
            for nombre in cargados
        ):
            return
        inicio_carga = self._reloj()
        motor.calentar(timeout=politica.carga)
        restante = self._restante(inicio_carga, politica.carga, "carga")
        cargados = motor.modelos_cargados(timeout=restante)
        self._comprobar_plazo(inicio_carga, politica.carga, "carga")
        if {
            normalizar_nombre_modelo(nombre) for nombre in cargados
        } != {configuracion.nombre}:
            raise ErrorRespuestaLLM(
                f"No se pudo confirmar la carga exclusiva de {configuracion.nombre}."
            )

    def _inferir(
        self,
        motor: _MotorGestionable,
        configuracion: ModeloConfigurado,
        historial: Sequence[Mapping[str, str]],
        herramientas: Sequence[Mapping[str, object]],
    ) -> RespuestaEstructurada:
        """Ejecuta una sola inferencia dentro del plazo configurado."""
        inicio = self._reloj()
        respuesta = motor.interpretar(historial, herramientas)
        self._comprobar_plazo(inicio, configuracion.politica.inferencia, "inferencia")
        return respuesta

    def _restante(self, inicio: float, limite: float, nombre: str) -> float:
        restante = limite - (self._reloj() - inicio)
        if restante <= 0:
            raise TimeoutError(f"Se agotó el plazo de {nombre} del planificador.")
        return restante

    def _comprobar_plazo(self, inicio: float, limite: float, nombre: str) -> None:
        if self._reloj() - inicio > limite:
            raise TimeoutError(f"Se agotó el plazo de {nombre} del planificador.")


def _crear_motor(
    configuracion: ModeloConfigurado,
) -> MotorOllama | MotorOllamaVision:
    """Crea un motor local sin elegir un modelo implícito."""
    if configuracion.rol == RolModelo.VOZ:
        raise MotorVozNoDisponible(
            "El rol VOZ está configurado, pero la transcripción no está implementada."
        )
    clase = (
        MotorOllamaVision
        if configuracion.rol in {RolModelo.VISION, RolModelo.OCR}
        else MotorOllama
    )
    return clase(modelo=configuracion.nombre, timeout=configuracion.politica.inferencia)
