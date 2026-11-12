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


def test_consulta_un_evento_por_titulo():
    aplicacion, usuario = _entorno()

    aplicacion.herramientas.obtener("agenda_crear_evento").ejecutar(
        usuario.id,
        {
            "titulo": "Dentista",
            "comienza": "2026-11-13T10:00:00+01:00",
            "termina": "2026-11-13T11:00:00+01:00",
            "ubicacion": "Clinica Sonrisa",
            "descripcion": "Llevar tarjeta sanitaria",
        },
    )

    resultado = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "cuando tengo el dentista?",
    )

    assert resultado["ok"] is True
    assert "Dentista" in resultado["datos"]
    assert "13/11/2026" in resultado["datos"]
    assert "10:00 a 11:00" in resultado["datos"]
    assert "Clinica Sonrisa" in resultado["datos"]
    assert "Llevar tarjeta sanitaria" in resultado["datos"]


def test_consulta_evento_sin_lugar_ni_notas():
    aplicacion, usuario = _entorno()

    aplicacion.herramientas.obtener("agenda_crear_evento").ejecutar(
        usuario.id,
        {
            "titulo": "Gimnasio",
            "comienza": "2026-11-13T16:00:00+01:00",
            "termina": "2026-11-13T17:00:00+01:00",
        },
    )

    resultado = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "cuando tengo el gimnasio?",
    )

    assert resultado["ok"] is True
    assert "Gimnasio" in resultado["datos"]
    assert "16:00 a 17:00" in resultado["datos"]
    assert "Lugar:" not in resultado["datos"]
    assert "Notas:" not in resultado["datos"]
