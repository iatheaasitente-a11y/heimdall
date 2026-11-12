"""Catálogo inyectable de modelos y políticas por rol."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import TypeGuard


def _es_numero_finito(valor: object) -> TypeGuard[int | float]:
    try:
        return (
            not isinstance(valor, bool)
            and isinstance(valor, (int, float))
            and isfinite(valor)
        )
    except (OverflowError, TypeError, ValueError):
        return False


class RolModelo(StrEnum):
    """Roles que pueden tener un modelo local configurado."""

    TEXTO = "texto"
    ENRUTADOR = "enrutador"
    VISION = "vision"
    OCR = "ocr"
    VOZ = "voz"


def normalizar_nombre_modelo(nombre: str) -> str:
    """Añade la etiqueta ``:latest`` cuando el modelo no especifica una.

    Raises:
        TypeError: Si el nombre no es texto.
        ValueError: Si el nombre está vacío o termina con una etiqueta vacía.
    """
    if not isinstance(nombre, str):
        raise TypeError("El nombre del modelo debe ser texto.")
    nombre = nombre.strip()
    if not nombre:
        raise ValueError("El nombre del modelo no puede estar vacío.")
    ultima_parte = nombre.rsplit("/", 1)[-1]
    if ":" not in ultima_parte:
        return f"{nombre}:latest"
    if ultima_parte.endswith(":"):
        raise ValueError("La etiqueta del modelo no puede estar vacía.")
    return nombre


@dataclass(frozen=True)
class PoliticaRol:
    """Límites de espera y confianza para un rol."""

    bloqueo: float
    descarga: float
    carga: float
    inferencia: float
    confianza_minima: float

    def __post_init__(self) -> None:
        """Valida los límites configurados para el rol.

        Raises:
            ValueError: Si un plazo no es positivo o la confianza sale de 0 a 1.
        """
        plazos = (self.bloqueo, self.descarga, self.carga, self.inferencia)
        if any(
            not _es_numero_finito(plazo) or plazo <= 0
            for plazo in plazos
        ):
            raise ValueError("Los plazos del rol deben ser números positivos y finitos.")
        if (
            not _es_numero_finito(self.confianza_minima)
            or not 0 <= self.confianza_minima <= 1
        ):
            raise ValueError("La confianza mínima debe estar entre cero y uno.")


@dataclass(frozen=True)
class ModeloConfigurado:
    """Nombre explícito de modelo y política asignada a un rol."""

    nombre: str
    politica: PoliticaRol
    rol: RolModelo | None = None

    def __post_init__(self) -> None:
        """Rechaza nombres vacíos o políticas inválidas.

        Raises:
            ValueError: Si el nombre está vacío.
            TypeError: Si el nombre o la política tienen tipos inválidos.
        """
        if not isinstance(self.politica, PoliticaRol):
            raise TypeError("La política del modelo debe ser PoliticaRol.")
        if self.rol is not None and not isinstance(self.rol, RolModelo):
            raise TypeError("El rol del modelo debe ser RolModelo.")
        object.__setattr__(self, "nombre", normalizar_nombre_modelo(self.nombre))


_POLITICAS = MappingProxyType(
    {
        RolModelo.TEXTO: PoliticaRol(150, 10, 60, 45, 0.70),
        RolModelo.ENRUTADOR: PoliticaRol(150, 10, 60, 15, 0.70),
        RolModelo.VISION: PoliticaRol(150, 10, 60, 60, 0.70),
        RolModelo.OCR: PoliticaRol(150, 10, 60, 60, 0.70),
        RolModelo.VOZ: PoliticaRol(150, 10, 60, 45, 0.70),
    }
)


class Catalogo:
    """Catálogo inmutable de modelos seleccionados explícitamente."""

    def __init__(
        self,
        modelos: Mapping[RolModelo, str],
        politicas: Mapping[RolModelo, PoliticaRol] | None = None,
    ) -> None:
        """Inyecta los modelos habilitados y sus límites por rol.

        Los roles ausentes quedan apagados; no se asigna un modelo implícito.

        Raises:
            TypeError: Si las claves o nombres tienen tipos inválidos.
            ValueError: Si un nombre de modelo está vacío.
        """
        politicas_por_rol = _POLITICAS if politicas is None else politicas
        configurados: dict[RolModelo, ModeloConfigurado] = {}
        for rol, nombre in modelos.items():
            if not isinstance(rol, RolModelo):
                raise TypeError("Las claves del catálogo deben ser RolModelo.")
            if rol not in politicas_por_rol:
                raise ValueError(f"No hay política configurada para {rol.value}.")
            configurados[rol] = ModeloConfigurado(
                nombre,
                politicas_por_rol[rol],
                rol,
            )
        self._modelos = MappingProxyType(configurados)

    def obtener(self, rol: RolModelo) -> ModeloConfigurado | None:
        """Devuelve el modelo del rol o ``None`` si está apagado."""
        if not isinstance(rol, RolModelo):
            raise TypeError("El rol debe ser RolModelo.")
        return self._modelos.get(rol)


def confianza_suficiente(valor: object, minimo: float) -> bool:
    """Comprueba confianza finita, numérica, acotada y suficiente."""
    try:
        return (
            _es_numero_finito(valor)
            and 0 <= valor <= 1
            and valor >= minimo
        )
    except (OverflowError, TypeError, ValueError):
        return False
