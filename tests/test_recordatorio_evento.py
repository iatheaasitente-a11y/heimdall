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


def test_programa_recordatorio_antes_de_un_evento():
    aplicacion, usuario = _entorno()

    aplicacion.herramientas.obtener("agenda_crear_evento").ejecutar(
        usuario.id,
        {
            "titulo": "Dentista",
            "comienza": "2026-11-13T10:00:00+01:00",
            "termina": "2026-11-13T11:00:00+01:00",
        },
    )

    propuesta = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "recuerdame el dentista 30 minutos antes",
    )

    assert propuesta["ok"] is True
    assert "30 minutos antes" in propuesta["datos"]
    assert "Responde si para confirmar" in propuesta["datos"]

    resultado = aplicacion.router.procesar(usuario.id, uuid4(), "si")

    assert resultado["ok"] is True
    assert resultado["datos"]["programado_para"] == (
        "2026-11-13T09:30:00+01:00"
    )
