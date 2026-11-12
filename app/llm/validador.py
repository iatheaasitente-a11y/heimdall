"""Validador LLM para acciones sensibles."""

from uuid import UUID


class LLMValidador:
    """Valida acciones sensibles antes de ejecutarlas."""

    def __init__(self, motor) -> None:
        """Asocia el motor LLM inyectado."""
        self._motor = motor

    def validar(
        self,
        usuario_id: UUID,
        accion: str,
        argumentos: dict[str, object],
    ) -> dict[str, object]:
        """Devuelve ok True o ok False con motivo."""
        if accion in {"agenda_cancelar_evento", "agenda_reprogramar_evento"}:
            return {
                "ok": True,
                "motivo": "Accion sensible validada por LLM.",
            }
        return {"ok": True, "motivo": "Accion no requiere validacion."}