from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.composicion import crear_composicion
from app.database.connection import crear_conexion
from app.database.esquema import aplicar_schema
from app.llm import MotorFalso

AHORA = datetime(2026, 11, 12, 14, 0, tzinfo=ZoneInfo("Europe/Madrid"))


def _entorno():
    conexion = crear_conexion(":memory:")
    aplicar_schema(conexion)
    aplicacion = crear_composicion(
        conexion,
        lambda: AHORA,
        motor=MotorFalso(),
    )
    usuario = aplicacion.usuarios.registrar(
        "Ana",
        zona_horaria="Europe/Madrid",
    )
    return aplicacion, usuario


def _crear_evento(aplicacion, usuario, titulo):
    aplicacion.herramientas.obtener("agenda_crear_evento").ejecutar(
        usuario.id,
        {
            "titulo": titulo,
            "comienza": "2026-11-16T10:00:00+01:00",
            "termina": "2026-11-16T11:00:00+01:00",
        },
    )


def test_cancelar_evento_requiere_confirmacion():
    aplicacion, usuario = _entorno()
    _crear_evento(aplicacion, usuario, "Gimnasio")

    propuesta = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "cancela el evento Gimnasio",
    )

    assert propuesta["ok"] is True
    assert "cancelar" in propuesta["datos"].lower()

    eventos = aplicacion.herramientas.obtener(
        "agenda_eventos_del_dia"
    ).ejecutar(
        usuario.id,
        {"dia": "2026-11-16"},
    )
    assert len(eventos["datos"]) == 1

    resultado = aplicacion.router.procesar(usuario.id, uuid4(), "si")

    assert resultado["ok"] is True
    assert resultado["datos"]["estado"] == "cancelado"


def test_completar_evento_requiere_confirmacion():
    aplicacion, usuario = _entorno()
    _crear_evento(aplicacion, usuario, "Gimnasio")

    propuesta = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "marca como completado el evento Gimnasio",
    )

    assert propuesta["ok"] is True
    assert "completado" in propuesta["datos"].lower()

    resultado = aplicacion.router.procesar(usuario.id, uuid4(), "si")

    assert resultado["ok"] is True
    assert resultado["datos"]["estado"] == "completado"


def test_cancelar_accion_pendiente():
    aplicacion, usuario = _entorno()
    _crear_evento(aplicacion, usuario, "Gimnasio")

    aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "cancela el evento Gimnasio",
    )

    resultado = aplicacion.router.procesar(usuario.id, uuid4(), "no")

    assert resultado["ok"] is True
    assert "cancelado" in resultado["datos"].lower()

    eventos = aplicacion.herramientas.obtener(
        "agenda_eventos_del_dia"
    ).ejecutar(
        usuario.id,
        {"dia": "2026-11-16"},
    )
    assert len(eventos["datos"]) == 1
