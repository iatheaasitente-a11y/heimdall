"""Agente personal con reglas deterministas antes de la interpretación LLM."""

from collections.abc import Callable, Mapping, Sequence
from datetime import date
import unicodedata
from uuid import UUID

from app.agents.base import AgenteBase
from app.llm.frenos import FrenosLLM
from app.llm.interfaz import MotorLLM
from app.tools.base import Herramienta
from app.tools.registro import RegistroHerramientas


class AgentePersonal(AgenteBase):
    """Enruta mensajes a herramientas, priorizando patrones deterministas."""

    def __init__(
        self,
        herramientas: RegistroHerramientas,
        motor: MotorLLM | None = None,
        hoy_por_usuario: Callable[[UUID], date] | None = None,
    ) -> None:
        """Configura el catálogo, el motor opcional y el contexto de fecha."""
        self._herramientas = herramientas
        self._frenos = FrenosLLM(motor) if motor is not None else None
        self._hoy_por_usuario = (
            hoy_por_usuario
            if hoy_por_usuario is not None
            else _hoy_local
        )

    def procesar(
        self,
        usuario_id: UUID,
        conversacion_id: UUID,
        texto: str,
        historial: Sequence[Mapping[str, str]] = (),
    ) -> dict[str, object] | None:
        """Aplica primero reglas y luego, si existe, consulta el motor LLM.

        Returns:
            Resultado JSON de una herramienta o ``None`` si no hay intención.

        Raises:
            KeyError: Si no está registrada la herramienta de resumen diario.
        """
        if _es_resumen_de_hoy(texto):
            return self._herramientas.obtener("resumen_del_dia").ejecutar(
                usuario_id,
                {"dia": self._hoy_por_usuario(usuario_id)},
            )
        if self._frenos is None:
            return None

        definiciones = [
            _definicion(herramienta) for herramienta in self._herramientas.listar()
        ]
        respuesta = self._frenos.consultar(
            conversacion_id,
            historial,
            definiciones,
        )
        if respuesta is None:
            return None
        try:
            herramienta = self._herramientas.obtener(respuesta.intencion)
        except KeyError:
            return None
        return herramienta.ejecutar(usuario_id, respuesta.campos)


def _hoy_local(usuario_id: UUID) -> date:
    """Devuelve la fecha local del proceso si no se inyecta una zona de usuario."""
    del usuario_id
    return date.today()


def _definicion(herramienta: Herramienta) -> dict[str, object]:
    """Representa una herramienta sin incluir el identificador del usuario."""
    return {
        "name": herramienta.nombre,
        "description": herramienta.descripcion,
        "parameters": herramienta.esquema_json(),
    }


def _es_resumen_de_hoy(texto: str) -> bool:
    """Reconoce unas pocas formas comunes de consultar el día actual."""
    normalizado = _normalizar(texto)
    return any(
        frase in normalizado
        for frase in ("que tengo hoy", "que tengo para hoy", "que hay hoy")
    )


def _normalizar(texto: str) -> str:
    """Pasa el mensaje a minúsculas sin diacríticos."""
    sin_acentos = unicodedata.normalize("NFKD", texto.casefold())
    caracteres = (
        caracter
        for caracter in sin_acentos
        if not unicodedata.combining(caracter)
    )
    return " ".join("".join(caracteres).split())
