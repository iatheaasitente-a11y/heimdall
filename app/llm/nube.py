"""Punto de extensión sin credenciales ni conexiones a servicios externos."""

from collections.abc import Mapping, Sequence

from app.llm.interfaz import MotorLLM, RespuestaEstructurada


class MotorNube(MotorLLM):
    """Esqueleto de motor remoto, deliberadamente sin acceso a red."""

    def interpretar(
        self,
        historial: Sequence[Mapping[str, str]],
        herramientas: Sequence[Mapping[str, object]],
    ) -> RespuestaEstructurada:
        """Indica que el motor remoto aún no está implementado.

        Raises:
            NotImplementedError: Este motor no hace solicitudes ni requiere claves.
        """
        del historial, herramientas
        raise NotImplementedError("MotorNube todavía no está implementado.")
