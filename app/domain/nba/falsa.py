"""Fuente NBA determinista para pruebas y desarrollo."""

from collections.abc import Mapping


class FuenteNBAFalsa:
    """Responde consultas configuradas sin acceder a una API externa."""

    def __init__(self, respuestas: Mapping[str, str]) -> None:
        """Copia las respuestas que devolverá la fuente falsa."""
        self._respuestas = dict(respuestas)

    def consultar(self, consulta: str) -> str:
        """Devuelve la respuesta configurada para la consulta.

        Raises:
            ValueError: Si no hay una respuesta configurada para la consulta.
        """
        try:
            return self._respuestas[consulta]
        except KeyError as error:
            raise ValueError(f"No hay datos NBA para «{consulta}».") from error
