"""Errores propios de resolución de nombres en herramientas."""


class ErrorResolucionNombre(ValueError):
    """Un nombre exacto no identifica de forma única una entidad del usuario."""

    def __init__(
        self,
        mensaje: str,
        candidatos: list[dict[str, str]],
    ) -> None:
        """Guarda el mensaje y los candidatos que pueden aclarar la selección."""
        super().__init__(mensaje)
        self.candidatos = candidatos
