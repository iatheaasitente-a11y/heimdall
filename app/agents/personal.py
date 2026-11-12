"""Agente personal con reglas deterministas antes de la interpretación LLM."""

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime
from uuid import UUID

from app.agents.base import AgenteBase
from app.agents.reglas import ReglasDeterministas
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
        ahora_por_usuario: Callable[[UUID], datetime] | None = None,
    ) -> None:
        """Configura el catálogo, el motor opcional y el contexto de fecha."""
        self._herramientas = herramientas
        self._frenos = FrenosLLM(motor) if motor is not None else None
        self._hoy_por_usuario = (
            hoy_por_usuario
            if hoy_por_usuario is not None
            else _hoy_local
        )
        self._reglas = ReglasDeterministas(
            herramientas,
            self._hoy_por_usuario,
            ahora_por_usuario,
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
        resultado_regla = self._reglas.procesar(usuario_id, texto)
        if resultado_regla is not None:
            return resultado_regla
        if self._frenos is None:
            return None

        historial_motor = _ultimos_cuatro_turnos(historial)
        esperando = _esperando(historial_motor)
        if esperando is not None:
            historial_motor.insert(
                0,
                {"role": "assistant", "content": f"esperando: {esperando}"},
            )
        definiciones = [
            _definicion(herramienta) for herramienta in self._herramientas.listar()
        ]
        respuesta = self._frenos.consultar(
            conversacion_id,
            historial_motor,
            definiciones,
        )
        if respuesta is None:
            return None
        try:
            herramienta = self._herramientas.obtener(respuesta.intencion)
        except KeyError:
            return None
        if not _campos_dentro_del_catalogo(herramienta, respuesta.campos):
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


def _ultimos_cuatro_turnos(
    historial: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    """Conserva los cuatro mensajes de usuario más recientes y su contexto."""
    indices_usuario = [
        indice
        for indice, mensaje in enumerate(historial)
        if mensaje.get("role") == "user"
    ]
    inicio = indices_usuario[-4] if len(indices_usuario) > 4 else 0
    return [dict(mensaje) for mensaje in historial[inicio:]]


def _esperando(historial: Sequence[Mapping[str, str]]) -> str | None:
    """Extrae la última pregunta del asistente para desambiguar la respuesta."""
    for mensaje in reversed(historial):
        if mensaje.get("role") != "assistant":
            continue
        contenido = mensaje.get("content", "")
        try:
            datos = json.loads(contenido)
        except json.JSONDecodeError:
            datos = None
        if isinstance(datos, dict) and datos.get("ok") is False:
            error = datos.get("error")
            return error if isinstance(error, str) else None
        if "¿" in contenido or contenido.rstrip().endswith("?"):
            return contenido
        return None
    return None


def _campos_dentro_del_catalogo(
    herramienta: Herramienta,
    campos: Mapping[str, object],
) -> bool:
    """Rechaza campos desconocidos o inválidos antes de ejecutar la herramienta."""
    esquema = herramienta.esquema_json()
    if not _valor_dentro_del_esquema(campos, esquema, esquema):
        return False
    try:
        herramienta.parametros.model_validate(dict(campos))
    except (TypeError, ValueError):
        return False
    return True


def _valor_dentro_del_esquema(
    valor: object,
    esquema: Mapping[str, object],
    raiz: Mapping[str, object],
) -> bool:
    """Comprueba recursivamente que objetos y listas no añadan propiedades."""
    esquema = _resolver_referencia(esquema, raiz)
    if isinstance(valor, Mapping):
        for rama in _ramas_esquema(esquema):
            if rama.get("type") != "object" and "properties" not in rama:
                continue
            propiedades = rama.get("properties", {})
            if not isinstance(propiedades, Mapping) or not set(valor) <= set(propiedades):
                continue
            if all(
                _valor_dentro_del_esquema(dato, propiedades[nombre], raiz)
                for nombre, dato in valor.items()
                if isinstance(propiedades.get(nombre), Mapping)
            ):
                return True
        return False
    if isinstance(valor, list):
        for rama in _ramas_esquema(esquema):
            if rama.get("type") != "array":
                continue
            elementos = rama.get("items")
            if isinstance(elementos, Mapping) and all(
                _valor_dentro_del_esquema(item, elementos, raiz) for item in valor
            ):
                return True
        return False
    return True


def _resolver_referencia(
    esquema: Mapping[str, object],
    raiz: Mapping[str, object],
) -> Mapping[str, object]:
    """Expande referencias locales a definiciones del esquema Pydantic."""
    referencia = esquema.get("$ref")
    if not isinstance(referencia, str) or not referencia.startswith("#/$defs/"):
        return esquema
    nombre = referencia.removeprefix("#/$defs/")
    definiciones = raiz.get("$defs")
    if not isinstance(definiciones, Mapping) or not isinstance(
        definiciones.get(nombre), Mapping
    ):
        return esquema
    expandido = dict(definiciones[nombre])
    expandido.update({clave: valor for clave, valor in esquema.items() if clave != "$ref"})
    return expandido


def _ramas_esquema(esquema: Mapping[str, object]) -> list[Mapping[str, object]]:
    """Aplana uniones JSON Schema para inspeccionar sus propiedades."""
    ramas = [esquema]
    for clave in ("anyOf", "oneOf", "allOf"):
        subesquemas = esquema.get(clave)
        if isinstance(subesquemas, list):
            ramas.extend(
                rama
                for subesquema in subesquemas
                if isinstance(subesquema, Mapping)
                for rama in _ramas_esquema(subesquema)
            )
    return ramas
