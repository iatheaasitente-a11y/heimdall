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


def test_crea_evento_con_lugar_y_notas():
    aplicacion, usuario = _entorno()

    propuesta = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "crea un evento dentista manana a las 10 durante 1 hora "
        "en la clinica sonrisa, llevar tarjeta",
    )

    assert propuesta["ok"] is True
    assert "Dentista" in propuesta["datos"]
    assert "Lugar: clinica sonrisa" in propuesta["datos"]
    assert "Notas: llevar tarjeta" in propuesta["datos"]

    resultado = aplicacion.router.procesar(usuario.id, uuid4(), "si")

    assert resultado["ok"] is True

    consulta = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "cuando tengo el dentista?",
    )

    assert consulta["ok"] is True
    assert "clinica sonrisa" in consulta["datos"]
    assert "llevar tarjeta" in consulta["datos"]


def test_crea_evento_con_notas_etiquetadas():
    aplicacion, usuario = _entorno()

    propuesta = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "crea un evento dentista manana a las 10 durante 1 hora "
        "en la clinica sonrisa, notas: llevar tarjeta",
    )

    assert propuesta["ok"] is True
    assert "Lugar: clinica sonrisa" in propuesta["datos"]
    assert "Notas: llevar tarjeta" in propuesta["datos"]


def test_crea_evento_sin_lugar_ni_notas():
    aplicacion, usuario = _entorno()

    propuesta = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "crea un evento gimnasio manana a las 16 durante 1 hora",
    )

    assert propuesta["ok"] is True
    assert "Lugar:" not in propuesta["datos"]
    assert "Notas:" not in propuesta["datos"]
