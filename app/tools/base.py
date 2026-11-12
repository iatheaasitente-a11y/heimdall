"""Contrato y ejecución segura de las herramientas disponibles para el agente."""

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Callable
from uuid import UUID

from pydantic import BaseModel

from app.services.errores import ErrorDeServicio

Ejecutor = Callable[[UUID, dict[str, Any]], object]


class Herramienta:
    """Herramienta con parámetros validados por un modelo Pydantic."""

    def __init__(
        self,
        nombre: str,
        descripcion: str,
        parametros: type[BaseModel],
        ejecutar: Ejecutor,
    ) -> None:
        """Crea una herramienta y asocia su esquema de argumentos y ejecutor."""
        self.nombre = nombre
        self.descripcion = descripcion
        self.parametros = parametros
        self._ejecutar = ejecutar

    def esquema_json(self) -> dict[str, Any]:
        """Devuelve el esquema JSON generado por el modelo de parámetros."""
        return self.parametros.model_json_schema()

    def ejecutar(
        self, usuario_id: UUID, argumentos: Mapping[str, Any]
    ) -> dict[str, object]:
        """Valida argumentos y ejecuta el servicio con el usuario del sistema.

        Raises:
            pydantic.ValidationError: Si los argumentos no cumplen el esquema.
        """
        parametros = self.parametros.model_validate(dict(argumentos))
        try:
            datos = self._ejecutar(usuario_id, parametros.model_dump())
        except ErrorDeServicio as error:
            return {"ok": False, "error": str(error)}
        return {"ok": True, "datos": _a_json(datos)}


def _a_json(valor: object) -> object:
    """Convierte resultados de dominio en tipos serializables como JSON."""
    if isinstance(valor, Enum):
        return valor.value
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    if isinstance(valor, UUID):
        return str(valor)
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if is_dataclass(valor) and not isinstance(valor, type):
        return {
            campo.name: _a_json(getattr(valor, campo.name))
            for campo in fields(valor)
        }
    if isinstance(valor, Mapping):
        return {str(clave): _a_json(dato) for clave, dato in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_a_json(elemento) for elemento in valor]
    raise TypeError(f"El resultado {type(valor).__name__} no se puede serializar como JSON.")
