"""Agente personal con reglas deterministas antes de la interpretación LLM."""

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime
from typing import TypedDict
from unicodedata import combining, normalize
from uuid import UUID

from app.agents.base import AgenteBase
from app.agents.reglas import ReglasDeterministas
from app.llm.frenos import FrenosLLM
from app.llm.interfaz import MotorLLM
from app.tools.base import Herramienta
from app.tools.registro import RegistroHerramientas

_HERRAMIENTAS_DESTRUCTIVAS = {
    "agenda_cancelar_evento",
    "agenda_completar_evento",
    "agenda_reprogramar_evento",
    "objetivos_pausar",
    "objetivos_reanudar",
    "objetivos_cancelar",
    "recordatorios_cancelar",
}


class _PropuestaPendiente(TypedDict):
    """Propuesta destructiva validada y vinculada al usuario y conversación."""

    usuario_id: str
    conversacion_id: str
    herramienta: str
    campos: dict[str, object]
    requiere_reconfirmacion: bool


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
        """Resuelve propuestas pendientes, aplica reglas y luego consulta el LLM.

        Returns:
            Resultado JSON de una herramienta o ``None`` si no hay intención.

        Raises:
            KeyError: Si no está registrada la herramienta de resumen diario.
        """
        pendiente = (
            _confirmacion_pendiente(
                historial,
                usuario_id,
                conversacion_id,
                self._herramientas,
            )
            if self._frenos is not None
            else None
        )
        decision = _decision_confirmacion(texto) if pendiente is not None else None
        if pendiente is not None and decision is True:
            if pendiente["requiere_reconfirmacion"] is True:
                return _repetir_confirmacion(pendiente)
            herramienta = self._herramientas.obtener(pendiente["herramienta"])
            return herramienta.ejecutar(usuario_id, pendiente["campos"])
        if pendiente is not None and decision is False:
            return {"ok": False, "error": "Propuesta rechazada; no se ejecutó."}

        resultado_regla = self._reglas.procesar(usuario_id, texto)
        if resultado_regla is not None:
            if pendiente is not None:
                return _conservar_pendiente(resultado_regla, pendiente)
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
            return _repetir_confirmacion(pendiente) if pendiente is not None else None
        try:
            herramienta = self._herramientas.obtener(respuesta.intencion)
        except KeyError:
            return _repetir_confirmacion(pendiente) if pendiente is not None else None
        if not _campos_dentro_del_catalogo(herramienta, respuesta.campos):
            return _repetir_confirmacion(pendiente) if pendiente is not None else None
        if herramienta.nombre in _HERRAMIENTAS_DESTRUCTIVAS:
            propuesta = _crear_confirmacion(
                herramienta,
                respuesta.campos,
                usuario_id,
                conversacion_id,
            )
            return _preguntar_confirmacion(propuesta)
        if pendiente is not None:
            return _repetir_confirmacion(pendiente)
        resultado = herramienta.ejecutar(usuario_id, respuesta.campos)
        return resultado


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


def _confirmacion_pendiente(
    historial: Sequence[Mapping[str, str]],
    usuario_id: UUID,
    conversacion_id: UUID,
    herramientas: RegistroHerramientas,
) -> _PropuestaPendiente | None:
    """Lee solo una propuesta de la aplicación ligada al usuario y conversación."""
    for mensaje in reversed(historial):
        if mensaje.get("role") != "assistant":
            continue
        try:
            datos = json.loads(mensaje.get("content", ""))
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(datos, dict):
            return None
        propuesta = datos.get("confirmacion_pendiente")
        if not isinstance(propuesta, dict):
            return None
        if (
            propuesta.get("usuario_id") != str(usuario_id)
            or propuesta.get("conversacion_id") != str(conversacion_id)
        ):
            return None
        nombre = propuesta.get("herramienta")
        campos = propuesta.get("campos")
        requiere_reconfirmacion = propuesta.get("requiere_reconfirmacion")
        if (
            not isinstance(nombre, str)
            or not isinstance(campos, Mapping)
            or not isinstance(requiere_reconfirmacion, bool)
        ):
            return None
        if nombre not in _HERRAMIENTAS_DESTRUCTIVAS:
            return None
        try:
            registrada = herramientas.obtener(nombre)
        except KeyError:
            return None
        if registrada is None or not _campos_dentro_del_catalogo(registrada, campos):
            return None
        return {
            "usuario_id": str(usuario_id),
            "conversacion_id": str(conversacion_id),
            "herramienta": nombre,
            "campos": dict(campos),
            "requiere_reconfirmacion": requiere_reconfirmacion,
        }
    return None


def _decision_confirmacion(texto: str) -> bool | None:
    """Reconoce respuestas afirmativas o negativas inequívocas."""
    normalizado = normalize("NFKD", texto.casefold())
    normalizado = "".join(
        caracter for caracter in normalizado if not combining(caracter)
    )
    palabras = " ".join(
        "".join(
            caracter
            for caracter in normalizado
            if caracter.isalnum() or caracter.isspace()
        )
        .split()
    )
    if palabras in {"si", "confirmo", "si confirmo", "confirmo si"}:
        return True
    if palabras in {"no", "cancelo", "no confirmo", "no lo hagas"}:
        return False
    return None


def _crear_confirmacion(
    herramienta: Herramienta,
    campos: Mapping[str, object],
    usuario_id: UUID,
    conversacion_id: UUID,
) -> _PropuestaPendiente:
    """Construye el estado pendiente con argumentos validados por el catálogo."""
    parametros = herramienta.parametros.model_validate(dict(campos))
    return {
        "usuario_id": str(usuario_id),
        "conversacion_id": str(conversacion_id),
        "herramienta": herramienta.nombre,
        "campos": parametros.model_dump(mode="json"),
        "requiere_reconfirmacion": False,
    }


def _preguntar_confirmacion(
    propuesta: _PropuestaPendiente,
) -> dict[str, object]:
    """Devuelve la propuesta pendiente sin ejecutar la operación."""
    nombre = propuesta["herramienta"]
    campos = propuesta["campos"]
    detalle = _resumen_operacion(nombre, campos)
    return {
        "ok": False,
        "error": f"Propuesta: {detalle} ¿Confirmas? Responde «sí» o «no».",
        "confirmacion_pendiente": dict(propuesta),
    }


def _repetir_confirmacion(
    propuesta: _PropuestaPendiente,
) -> dict[str, object]:
    """Repite la misma propuesta sin cambiar herramienta ni argumentos."""
    if propuesta.get("requiere_reconfirmacion") is True:
        propuesta_actualizada: _PropuestaPendiente = {
            **propuesta,
            "requiere_reconfirmacion": False,
        }
        return _preguntar_confirmacion(propuesta_actualizada)
    return _preguntar_confirmacion(propuesta)


def _conservar_pendiente(
    resultado: dict[str, object],
    propuesta: _PropuestaPendiente,
) -> dict[str, object]:
    """Conserva una propuesta al atender una solicitud distinta."""
    salida = dict(resultado)
    propuesta_actualizada: _PropuestaPendiente = {
        **propuesta,
        "requiere_reconfirmacion": True,
    }
    salida["confirmacion_pendiente"] = propuesta_actualizada
    salida["mensaje"] = (
        "La propuesta anterior sigue pendiente; se volverá a mostrar "
        "antes de aceptar una confirmación."
    )
    return salida


def _resumen_operacion(nombre: object, campos: object) -> str:
    """Describe el objetivo y los cambios concretos de una operación."""
    if not isinstance(campos, Mapping) or not isinstance(nombre, str):
        return "la operación solicitada"
    if nombre == "agenda_reprogramar_evento":
        objetivo = _elemento_afectado(campos, "titulo", "evento_id")
        return (
            f"reprogramar el evento {objetivo}: nuevo inicio "
            f"{campos.get('comienza')} y nuevo fin {campos.get('termina')}."
        )
    acciones = {
        "agenda_cancelar_evento": ("cancelar el evento", "titulo", "evento_id"),
        "agenda_completar_evento": ("completar el evento", "titulo", "evento_id"),
        "objetivos_pausar": ("pausar el objetivo", "nombre", "objetivo_id"),
        "objetivos_reanudar": ("reanudar el objetivo", "nombre", "objetivo_id"),
        "objetivos_cancelar": ("cancelar el objetivo", "nombre", "objetivo_id"),
        "recordatorios_cancelar": (
            "cancelar el recordatorio",
            "mensaje",
            "recordatorio_id",
        ),
    }
    accion = acciones.get(nombre)
    if accion is None:
        return "la operación solicitada"
    verbo, selector, identificador = accion
    return f"{verbo} {_elemento_afectado(campos, selector, identificador)}."


def _elemento_afectado(
    campos: Mapping[str, object],
    selector: str,
    identificador: str,
) -> str:
    """Devuelve el nombre o identificador validado del elemento afectado."""
    valor = campos.get(selector) or campos.get(identificador)
    if isinstance(valor, (str, UUID)):
        return f"«{valor}»"
    return "indicado"


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
