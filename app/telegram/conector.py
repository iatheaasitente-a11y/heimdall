"""Conector de texto con Telegram Bot API y transporte inyectable."""

import json
import logging
import math
import re
from collections.abc import Callable, Mapping
from typing import Protocol
from urllib.request import Request, urlopen
from datetime import date
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.agents.router import Router
from app.domain.message import Conversacion, RolMensaje
from app.domain.relations import historial_para_modelo
from app.services.conversaciones import ServicioConversaciones
from app.services.recordatorios import ServicioRecordatorios
from app.services.usuarios import ServicioUsuarios
from app.telegram.configuracion import ConfiguracionTelegram, normalizar_chat_id

_LOG = logging.getLogger(__name__)
_MAX_CARACTERES = 4096
_PREFERENCIA_ZONA_CONFIRMADA = "telegram_zona_confirmada"
_METADATO_PENDIENTE_ZONA = "telegram_solicitud_pendiente_zona"
_METADATO_CONFIGURACION = "telegram_configuracion"
_UUID_TEXTO = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
Transporte = Callable[[Request, float], bytes]


class ErrorTelegram(Exception):
    """Error de protocolo Telegram redactado sin credenciales."""


class Parada(Protocol):
    """Predicado que termina el ciclo de long polling."""

    def __call__(self) -> bool: ...


class ConectorTelegram:
    """Procesa mensajes de chats permitidos por el mismo router del teclado."""

    def __init__(
        self,
        configuracion: ConfiguracionTelegram,
        chat_a_usuario: Mapping[str, UUID | str],
        usuarios: ServicioUsuarios,
        conversaciones: ServicioConversaciones,
        router: Router,
        *,
        confirmar: Callable[[], None],
        revertir: Callable[[], None],
        pausar_error: Callable[[], None],
        recordatorios: ServicioRecordatorios | None = None,
        transporte: Transporte | None = None,
    ) -> None:
        """Inyecta configuración, servicios y ciclo transaccional por actualización.

        Raises:
            ValueError: Si el mapeo contiene un ID de chat o UUID inválido.
        """
        self._configuracion = configuracion
        self._chat_a_usuario: dict[str, UUID] = {}
        for chat_id, usuario_id_raw in chat_a_usuario.items():
            try:
                usuario_id = (
                    usuario_id_raw
                    if isinstance(usuario_id_raw, UUID)
                    else UUID(usuario_id_raw)
                )
            except (TypeError, ValueError) as error:
                raise ValueError(
                    "El mapeo debe asociar chats con UUID de usuario."
                ) from error
            self._chat_a_usuario[normalizar_chat_id(chat_id)] = usuario_id
        self._usuario_a_chat = {
            usuario_id: chat_id
            for chat_id, usuario_id in self._chat_a_usuario.items()
        }
        self._usuarios = usuarios
        self._conversaciones = conversaciones
        self._router = router
        self._confirmar = confirmar
        self._revertir = revertir
        self._pausar_error = pausar_error
        self._recordatorios = recordatorios
        self._transporte = _transporte_urllib if transporte is None else transporte
        self._offset: int | None = None
        self._habilitado = bool(
            configuracion.habilitada
            and configuracion.chat_ids & self._chat_a_usuario.keys()
        )
        if configuracion.habilitada and not self._habilitado:
            _LOG.error("Telegram cerrado: no hay asociaciones de chat con usuarios.")

    def obtener_actualizaciones(
        self,
        espera: int,
        timeout_http: float,
    ) -> list[dict[str, object]]:
        """Obtiene actualizaciones mediante long polling ``getUpdates``.

        Raises:
            ValueError: Si los límites de espera no son válidos.
            ErrorTelegram: Si Telegram devuelve una respuesta inválida.
        """
        if not self._habilitado:
            return []
        _validar_esperas(espera, timeout_http)
        parametros: dict[str, object] = {
            "timeout": espera,
            "allowed_updates": ["message"],
        }
        if self._offset is not None:
            parametros["offset"] = self._offset
        respuesta = self._solicitar("getUpdates", parametros, timeout_http)
        resultado = respuesta.get("result")
        if not isinstance(resultado, list):
            raise ErrorTelegram("Telegram devolvió actualizaciones inválidas.")
        actualizaciones: list[dict[str, object]] = []
        for actualizacion in resultado:
            if not isinstance(actualizacion, dict):
                raise ErrorTelegram("Telegram devolvió una actualización inválida.")
            update_id = actualizacion.get("update_id")
            if isinstance(update_id, bool) or not isinstance(update_id, int):
                raise ErrorTelegram("Telegram devolvió una actualización inválida.")
            actualizaciones.append(actualizacion)
        return actualizaciones

    def procesar_actualizacion(
        self,
        actualizacion: Mapping[str, object],
        timeout_http: float,
    ) -> None:
        """Autoriza, registra y enruta una actualización de texto.

        Las entradas de chats no permitidos o sin asociación se ignoran.

        Raises:
            ValueError: Si el timeout HTTP no es válido.
            ErrorTelegram: Si Telegram devuelve errores o datos inválidos.
        """
        if not self._habilitado:
            return
        _validar_timeout_http(timeout_http)
        mensaje = actualizacion.get("message")
        if not isinstance(mensaje, dict):
            return
        chat = mensaje.get("chat")
        if not isinstance(chat, dict) or chat.get("type") != "private":
            return
        chat_id = _id_desde_actualizacion(chat.get("id"))
        if (
            chat_id is None
            or chat_id not in self._configuracion.chat_ids
            or chat_id not in self._chat_a_usuario
        ):
            return
        texto = mensaje.get("text")
        if not isinstance(texto, str) or not texto.strip():
            return
        texto = texto.strip()
        usuario_id = self._chat_a_usuario[chat_id]
        usuario = self._usuarios.obtener(usuario_id)
        if not usuario.activo:
            return
        conversacion = self._obtener_conversacion(usuario_id)
        if usuario.preferencias.get(_PREFERENCIA_ZONA_CONFIRMADA) is True:
            self._procesar_texto(
                chat_id,
                usuario_id,
                conversacion.id,
                texto,
                timeout_http,
            )
            return
        self._confirmar_zona_y_procesar(
            chat_id,
            usuario_id,
            conversacion.id,
            texto,
            timeout_http,
        )

    def enviar_recordatorios_vencidos(self, timeout_http: float) -> int:
        """Envia los recordatorios vencidos y los marca como enviados."""

        if self._recordatorios is None or not self._habilitado:
            return 0

        enviados = 0

        for recordatorio in self._recordatorios.vencidos():
            chat_id = self._usuario_a_chat.get(recordatorio.usuario_id)

            if chat_id is None:
                continue

            try:
                self._enviar_texto(
                    chat_id,
                    f"Recordatorio: {recordatorio.mensaje}",
                    timeout_http,
                )
            except ErrorTelegram:
                continue

            self._recordatorios.marcar_enviado(recordatorio.id)
            enviados += 1

        return enviados

    def ejecutar(
        self,
        espera: int,
        timeout_http: float,
        detener: Parada,
    ) -> None:
        """Procesa actualizaciones aisladas hasta que ``detener`` devuelve ``True``.

        Cada actualización exitosa se confirma antes de avanzar el offset. Ante
        un fallo se revierte, se registra solo el tipo de error y se pausa.

        Raises:
            ValueError: Si los límites de espera no son válidos.
        """
        if not self._habilitado:
            return
        _validar_esperas(espera, timeout_http)
        while self._habilitado and not detener():
            try:
                actualizaciones = self.obtener_actualizaciones(espera, timeout_http)
            except Exception as error:
                self._registrar_error("consulta", error)
                self._pausar_error()
                continue
            for actualizacion in actualizaciones:
                try:
                    update_id = _validar_update_id(actualizacion)
                    self.procesar_actualizacion(actualizacion, timeout_http)
                    self._confirmar()
                except Exception as error:
                    try:
                        self._revertir()
                    except Exception as error_reversion:
                        self._registrar_error("reversión", error_reversion)
                        raise ErrorTelegram(
                            "No se pudo revertir la actualización de Telegram."
                        ) from None
                    self._registrar_error("actualización", error)
                    self._pausar_error()
                    break
                self._offset = max(self._offset or 0, update_id + 1)

    @staticmethod
    def _registrar_error(etapa: str, error: Exception) -> None:
        """Registra solo la etapa y el tipo, nunca mensajes potencialmente sensibles."""
        _LOG.error(
            "Error de Telegram durante %s (%s).",
            etapa,
            type(error).__name__,
        )

    def _confirmar_zona_y_procesar(
        self,
        chat_id: str,
        usuario_id: UUID,
        conversacion_id: UUID,
        texto: str,
        timeout_http: float,
    ) -> None:
        """Solicita una zona válida y después enruta la solicitud guardada."""
        mensajes = self._conversaciones.listar_mensajes(usuario_id, conversacion_id)
        pendiente = next(
            (
                mensaje
                for mensaje in reversed(mensajes)
                if mensaje.metadatos.get(_METADATO_PENDIENTE_ZONA) is True
            ),
            None,
        )
        if pendiente is None:
            self._conversaciones.agregar_mensaje(
                usuario_id,
                conversacion_id,
                RolMensaje.USUARIO,
                texto,
                {_METADATO_PENDIENTE_ZONA: True},
            )
            self._responder(
                chat_id,
                conversacion_id,
                "Antes de activar Telegram, indica tu zona horaria IANA "
                "(por ejemplo, Europe/Madrid).",
                timeout_http,
            )
            return

        self._conversaciones.agregar_mensaje(
            usuario_id,
            conversacion_id,
            RolMensaje.USUARIO,
            texto,
            {_METADATO_CONFIGURACION: "zona_horaria"},
        )
        try:
            ZoneInfo(texto.strip())
        except (ZoneInfoNotFoundError, ValueError):
            self._responder(
                chat_id,
                conversacion_id,
                "No reconocí esa zona horaria. Indica un nombre IANA, "
                "por ejemplo, Europe/Madrid.",
                timeout_http,
            )
            return
        self._usuarios.cambiar_zona_horaria(usuario_id, texto.strip())
        salida = self._crear_salida(
            usuario_id,
            conversacion_id,
            pendiente.contenido,
        )
        self._usuarios.cambiar_preferencia(
            usuario_id,
            _PREFERENCIA_ZONA_CONFIRMADA,
            True,
        )
        self._enviar_salida(
            chat_id,
            conversacion_id,
            salida,
            timeout_http,
        )

    def _procesar_texto(
        self,
        chat_id: str,
        usuario_id: UUID,
        conversacion_id: UUID,
        texto: str,
        timeout_http: float,
    ) -> None:
        self._conversaciones.agregar_mensaje(
            usuario_id,
            conversacion_id,
            RolMensaje.USUARIO,
            texto,
        )
        salida = self._crear_salida(usuario_id, conversacion_id, texto)
        self._enviar_salida(chat_id, conversacion_id, salida, timeout_http)

    def _crear_salida(
        self,
        usuario_id: UUID,
        conversacion_id: UUID,
        texto: str,
    ) -> dict[str, object]:
        mensajes = self._conversaciones.listar_mensajes(usuario_id, conversacion_id)
        contexto = [
            mensaje
            for mensaje in mensajes
            if _METADATO_CONFIGURACION not in mensaje.metadatos
        ]
        historial = historial_para_modelo(contexto)
        resultado = self._router.procesar(
            usuario_id,
            conversacion_id,
            texto,
            historial,
        )
        return resultado or {
            "ok": False,
            "error": "No he podido interpretar la solicitud.",
        }

    def _enviar_salida(
        self,
        chat_id: str,
        conversacion_id: UUID,
        salida: dict[str, object],
        timeout_http: float,
    ) -> None:
        contenido = json.dumps(salida, ensure_ascii=False)
        self._conversaciones.agregar_mensaje(
            self._chat_a_usuario[chat_id],
            conversacion_id,
            RolMensaje.ASISTENTE,
            contenido,
            {"resultado": salida},
        )
        self._enviar_texto(
            chat_id,
            formatear_respuesta(salida),
            timeout_http,
        )

    def _responder(
        self,
        chat_id: str,
        conversacion_id: UUID,
        texto: str,
        timeout_http: float,
    ) -> None:
        self._conversaciones.agregar_mensaje(
            self._chat_a_usuario[chat_id],
            conversacion_id,
            RolMensaje.ASISTENTE,
            texto,
            {_METADATO_CONFIGURACION: "zona_horaria"},
        )
        self._enviar_texto(chat_id, texto, timeout_http)

    def _enviar_texto(self, chat_id: str, texto: str, timeout_http: float) -> None:
        for inicio in range(0, len(texto), _MAX_CARACTERES):
            self._solicitar(
                "sendMessage",
                {
                    "chat_id": int(chat_id),
                    "text": texto[inicio : inicio + _MAX_CARACTERES],
                },
                timeout_http,
            )

    def _obtener_conversacion(self, usuario_id: UUID) -> Conversacion:
        conversaciones = self._conversaciones.listar_conversaciones(
            usuario_id,
            solo_activas=True,
        )
        if conversaciones:
            return conversaciones[0]
        return self._conversaciones.iniciar_conversacion(usuario_id, "Telegram")

    def _solicitar(
        self,
        metodo: str,
        parametros: Mapping[str, object],
        timeout: float,
    ) -> dict[str, object]:
        _validar_timeout_http(timeout)
        solicitud = Request(
            f"https://api.telegram.org/bot{self._configuracion.token}/{metodo}",
            data=json.dumps(parametros, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            contenido = self._transporte(solicitud, timeout)
        except OSError:
            _LOG.error("Falló la comunicación con Telegram en %s.", metodo)
            raise ErrorTelegram("No se pudo completar la solicitud a Telegram.") from None
        try:
            respuesta = json.loads(contenido.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ErrorTelegram("Telegram devolvió una respuesta inválida.") from None
        if not isinstance(respuesta, dict) or respuesta.get("ok") is not True:
            raise ErrorTelegram(f"Telegram rechazó la operación {metodo}.")
        return respuesta


def _id_desde_actualizacion(valor: object) -> str | None:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor == 0:
        return None
    return str(valor)


def _formatear_resumen(datos: Mapping[str, object]) -> str:
    """Convierte el resumen del día en una respuesta natural."""

    dias = {
        0: "lunes",
        1: "martes",
        2: "miércoles",
        3: "jueves",
        4: "viernes",
        5: "sábado",
        6: "domingo",
    }
    meses = {
        1: "enero",
        2: "febrero",
        3: "marzo",
        4: "abril",
        5: "mayo",
        6: "junio",
        7: "julio",
        8: "agosto",
        9: "septiembre",
        10: "octubre",
        11: "noviembre",
        12: "diciembre",
    }

    try:
        fecha = date.fromisoformat(str(datos.get("dia", "")))
        fecha_texto = (
            f"{dias[fecha.weekday()]} {fecha.day} de "
            f"{meses[fecha.month]} de {fecha.year}"
        )
    except (TypeError, ValueError):
        fecha_texto = str(datos.get("dia", "hoy"))

    eventos = datos.get("eventos") or []
    habitos = datos.get("habitos_pendientes") or []
    recordatorios = datos.get("recordatorios") or []

    if not eventos and not habitos and not recordatorios:
        return _embellecer(
            f"Hoy, {fecha_texto}, no tienes eventos ni recordatorios."
        )

    partes = [f"Hoy, {fecha_texto}:"]

    if eventos:
        detalles = []
        for evento in eventos:
            if not isinstance(evento, Mapping):
                continue
            titulo = evento.get("titulo", "Evento")
            inicio = evento.get("inicio", "")
            fin = evento.get("fin", "")
            detalles.append(f"• {titulo} — {inicio} a {fin}")
        partes.append("Eventos:")
        partes.extend(detalles)

    if recordatorios:
        partes.append("Recordatorios:")
        partes.extend(f"• {mensaje}" for mensaje in recordatorios)

    if habitos:
        partes.append("Hábitos pendientes:")
        partes.extend(f"• {nombre}" for nombre in habitos)

    return _embellecer("\n".join(partes))




def _embellecer(texto: str) -> str:
    """Mejora la presentacion: mayusculas, vinetas y puntuacion."""

    lineas = []

    for linea in texto.split("\n"):
        linea = re.sub(
            r"^(\s*[\u2022\-]\s*)([a-z\u00e1-\u00ff])",
            lambda coincidencia: (
                coincidencia.group(1)
                + coincidencia.group(2).upper()
            ),
            linea,
        )

        if linea and linea[0].isalpha():
            linea = linea[0].upper() + linea[1:]

        lineas.append(linea)

    texto = "\n".join(lineas)

    texto = re.sub(
        r"(?<=[.!?]\s)([a-z\u00e1-\u00ff])",
        lambda coincidencia: coincidencia.group(1).upper(),
        texto,
    )

    return texto

def formatear_respuesta(salida: Mapping[str, object]) -> str:
    """Convierte una salida interna a texto y omite identificadores UUID.

    Las respuestas no exitosas incluyen los nombres de candidatos, nunca sus
    UUID. Los identificadores que aparezcan en textos se redactan.
    """
    if salida.get("ok") is True:
        datos = salida.get("datos")
        if isinstance(datos, Mapping) and {
            "dia",
            "eventos",
            "habitos_pendientes",
            "recordatorios",
        } <= set(datos):
            return _formatear_resumen(datos)
        texto = _formatear_valor(datos)
        return _embellecer(texto or "Solicitud completada.")
    error = salida.get("error")
    texto = _redactar_uuid(error) if isinstance(error, str) else (
        "No he podido interpretar la solicitud."
    )
    candidatos = salida.get("candidatos")
    nombres = [
        _redactar_uuid(candidato["nombre"])
        for candidato in candidatos
        if isinstance(candidato, Mapping)
        and isinstance(candidato.get("nombre"), str)
        and candidato["nombre"].strip()
    ] if isinstance(candidatos, list) else []
    if nombres:
        texto = f"{texto} Opciones: {', '.join(nombres)}."
    return texto


def _formatear_valor(valor: object) -> str:
    """Aplana datos de respuesta en texto sin incluir campos identificadores."""
    if isinstance(valor, Mapping):
        partes = []
        for clave, dato in valor.items():
            if not isinstance(clave, str):
                continue
            clave_normalizada = clave.casefold()
            if clave_normalizada == "id" or clave_normalizada.endswith("_id"):
                continue
            contenido = _formatear_valor(dato)
            if contenido:
                etiqueta = clave.replace("_", " ").capitalize()
                partes.append(f"{etiqueta}: {contenido}")
        return "; ".join(partes)
    if isinstance(valor, list):
        return "; ".join(
            contenido
            for elemento in valor
            if (contenido := _formatear_valor(elemento))
        )
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    if isinstance(valor, (str, int, float)):
        return _redactar_uuid(str(valor))
    return ""


def _redactar_uuid(texto: str) -> str:
    """Sustituye UUID por una etiqueta no identificadora."""
    return _UUID_TEXTO.sub("[identificador]", texto)


def _validar_update_id(actualizacion: Mapping[str, object]) -> int:
    """Obtiene el ID de una actualización antes de procesarla."""
    update_id = actualizacion.get("update_id")
    if isinstance(update_id, bool) or not isinstance(update_id, int):
        raise ErrorTelegram("Telegram devolvió una actualización inválida.")
    return update_id


def _validar_esperas(espera: int, timeout_http: float) -> None:
    if isinstance(espera, bool) or not isinstance(espera, int) or not 1 <= espera <= 50:
        raise ValueError("La espera de long polling debe estar entre 1 y 50 segundos.")
    _validar_timeout_http(timeout_http)
    if timeout_http <= espera:
        raise ValueError("El timeout HTTP debe ser mayor que la espera.")


def _validar_timeout_http(timeout: float) -> None:
    try:
        valido = (
            not isinstance(timeout, bool)
            and isinstance(timeout, (int, float))
            and math.isfinite(timeout)
            and timeout > 0
        )
    except (OverflowError, TypeError, ValueError):
        valido = False
    if not valido:
        raise ValueError("El timeout HTTP debe ser positivo y finito.")


def _transporte_urllib(solicitud: Request, timeout: float) -> bytes:
    """Envía una solicitud con urllib sin exponer errores con URL completa."""
    try:
        with urlopen(solicitud, timeout=timeout) as respuesta:
            return respuesta.read()
    except OSError:
        raise OSError("Falló el transporte HTTP de Telegram.") from None
