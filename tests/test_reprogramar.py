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


def test_reprograma_evento_con_confirmacion():
    aplicacion, usuario = _entorno()

    aplicacion.herramientas.obtener("agenda_crear_evento").ejecutar(
        usuario.id,
        {
            "titulo": "Gimnasio",
            "comienza": "2026-11-16T10:00:00+01:00",
            "termina": "2026-11-16T11:00:00+01:00",
        },
    )

    propuesta = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "mueve el evento Gimnasio al viernes a las 16 durante 1 hora",
    )

    assert propuesta["ok"] is True
    assert "13/11/2026 16:00" in propuesta["datos"]
    assert "Responde si para confirmar" in propuesta["datos"]

    resultado = aplicacion.router.procesar(usuario.id, uuid4(), "si")

    assert resultado["ok"] is True
    assert resultado["datos"]["comienza"] == "2026-11-13T16:00:00+01:00"
    assert resultado["datos"]["termina"] == "2026-11-13T17:00:00+01:00"


def test_reprograma_conservando_la_duracion_original():
    aplicacion, usuario = _entorno()

    aplicacion.herramientas.obtener("agenda_crear_evento").ejecutar(
        usuario.id,
        {
            "titulo": "Gimnasio",
            "comienza": "2026-11-16T10:00:00+01:00",
            "termina": "2026-11-16T11:00:00+01:00",
        },
    )

    propuesta = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "mueve el evento Gimnasio al viernes a las 16",
    )

    assert propuesta["ok"] is True
    assert "13/11/2026 16:00 a 17:00" in propuesta["datos"]

    resultado = aplicacion.router.procesar(usuario.id, uuid4(), "si")

    assert resultado["ok"] is True
    assert resultado["datos"]["comienza"] == "2026-11-13T16:00:00+01:00"
    assert resultado["datos"]["termina"] == "2026-11-13T17:00:00+01:00"


def test_consulta_evento_por_titulo():
    aplicacion, usuario = _entorno()

    aplicacion.herramientas.obtener("agenda_crear_evento").ejecutar(
        usuario.id,
        {
            "titulo": "Gimnasio",
            "comienza": "2026-11-16T10:00:00+01:00",
            "termina": "2026-11-16T11:00:00+01:00",
        },
    )

    resultado = aplicacion.herramientas.obtener(
        "agenda_consultar_evento"
    ).ejecutar(
        usuario.id,
        {"evento_id": None, "titulo": "Gimnasio"},
    )

    assert resultado["ok"] is True
    assert resultado["datos"]["titulo"] == "Gimnasio"


def test_cancela_recordatorio_con_confirmacion():
    aplicacion, usuario = _entorno()

    aplicacion.herramientas.obtener("recordatorios_programar").ejecutar(
        usuario.id,
        {
            "mensaje": "llamar a mamá",
            "cuando": "2026-11-13T10:00:00+01:00",
        },
    )

    propuesta = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "cancela el recordatorio llamar a mamá",
    )

    assert propuesta["ok"] is True
    assert "cancelar el recordatorio" in propuesta["datos"].lower()

    resultado = aplicacion.router.procesar(usuario.id, uuid4(), "si")

    assert resultado["ok"] is True
    assert resultado["datos"]["estado"] == "cancelado"
