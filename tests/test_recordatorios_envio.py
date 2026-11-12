import json
import sqlite3
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.composicion import crear_composicion
from app.database.esquema import aplicar_schema
from app.domain.reminder import EstadoRecordatorio
from app.llm import MotorFalso
from app.telegram.configuracion import ConfiguracionTelegram
from app.telegram.conector import ConectorTelegram


class Reloj:
    def __init__(self, momento):
        self.momento = momento

    def __call__(self):
        return self.momento


class TransporteFalso:
    def __init__(self):
        self.solicitudes = []

    def __call__(self, solicitud, timeout):
        self.solicitudes.append((solicitud, timeout))
        return b'{"ok":true,"result":[]}'


class RouterFalso:
    def procesar(self, usuario_id, conversacion_id, texto, historial):
        return {"ok": True, "datos": {"mensaje": "recibido"}}


AHORA = datetime(2026, 11, 12, 14, 0, tzinfo=ZoneInfo("Europe/Madrid"))


def _entorno():
    conexion = sqlite3.connect(":memory:")
    conexion.row_factory = sqlite3.Row
    aplicar_schema(conexion)

    reloj = Reloj(AHORA)
    aplicacion = crear_composicion(
        conexion,
        reloj,
        motor=MotorFalso(),
    )
    usuario = aplicacion.usuarios.registrar(
        "Ana",
        zona_horaria="Europe/Madrid",
    )
    return aplicacion, usuario, reloj


def _conector(aplicacion, usuario, transporte):
    return ConectorTelegram(
        ConfiguracionTelegram("credencial-prueba", frozenset({"123"})),
        {"123": usuario.id},
        aplicacion.usuarios,
        aplicacion.conversaciones,
        RouterFalso(),
        confirmar=lambda: None,
        revertir=lambda: None,
        pausar_error=lambda: None,
        transporte=transporte,
        recordatorios=aplicacion.recordatorios,
    )


def test_envia_un_recordatorio_vencido_una_vez():
    aplicacion, usuario, reloj = _entorno()
    transporte = TransporteFalso()
    conector = _conector(aplicacion, usuario, transporte)

    aplicacion.recordatorios.programar(
        usuario.id,
        "llamar a mama",
        AHORA + timedelta(minutes=1),
    )

    reloj.momento = AHORA + timedelta(minutes=2)
    enviados = conector.enviar_recordatorios_vencidos(15)

    assert enviados == 1
    assert len(transporte.solicitudes) == 1

    texto = json.loads(transporte.solicitudes[0][0].data)["text"]
    assert "llamar a mama" in texto

    recordatorios = aplicacion.recordatorios.listar_recordatorios(usuario.id)
    assert recordatorios[0].estado == EstadoRecordatorio.ENVIADO

    assert conector.enviar_recordatorios_vencidos(15) == 0


def test_no_envia_recordatorios_futuros():
    aplicacion, usuario, _reloj = _entorno()
    transporte = TransporteFalso()
    conector = _conector(aplicacion, usuario, transporte)

    aplicacion.recordatorios.programar(
        usuario.id,
        "llamar a mama",
        AHORA + timedelta(hours=1),
    )

    assert conector.enviar_recordatorios_vencidos(15) == 0
    assert transporte.solicitudes == []
