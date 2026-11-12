"""Resolución de entidades propias a partir de un nombre exacto."""

import unicodedata
from collections.abc import Callable, Sequence
from typing import Protocol, TypeVar
from uuid import UUID

from app.services.errores import ErrorResolucionNombre


class Identificable(Protocol):
    """Entidad con UUID para mostrar candidatos al usuario."""

    id: UUID


T = TypeVar("T", bound=Identificable)


def resolver_por_nombre(
    nombre: str,
    elementos: Sequence[T],
    etiqueta: Callable[[T], str],
    tipo: str,
) -> UUID:
    """Resuelve un nombre exacto entre los elementos de un usuario.

    Raises:
        ErrorResolucionNombre: Si no hay coincidencias únicas.
    """
    normalizado = _normalizar(nombre)
    coincidencias = [
        elemento
        for elemento in elementos
        if _normalizar(etiqueta(elemento)) == normalizado
    ]
    candidatos = [
        {"id": str(elemento.id), "nombre": etiqueta(elemento)}
        for elemento in coincidencias
    ]
    if len(coincidencias) == 1:
        return coincidencias[0].id
    if coincidencias:
        mensaje = f"Hay varios {tipo} con el nombre «{nombre}»."
    else:
        mensaje = f"No encontré coincidencias de {tipo} para «{nombre}»."
    raise ErrorResolucionNombre(mensaje, candidatos)


def _normalizar(texto: str) -> str:
    """Compara ignorando mayúsculas, tildes y espacios exteriores."""
    descompuesto = unicodedata.normalize("NFKD", texto.casefold().strip())
    return "".join(
        caracter
        for caracter in descompuesto
        if not unicodedata.combining(caracter)
    )
