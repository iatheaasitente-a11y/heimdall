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


def _crear_gimnasio(aplicacion, usuario):
    aplicacion.herramientas.obtener("agenda_crear_evento").ejecutar(
        usuario.id,
        {
            "titulo": "Gimnasio",
            "comienza": "2026-11-13T16:00:00+01:00",
            "termina": "2026-11-13T17:00:00+01:00",
        },
    )


def test_propone_opciones_cuando_hay_conflicto():
    aplicacion, usuario = _entorno()
    _crear_gimnasio(aplicacion, usuario)

    resultado = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "crea un evento dentista manana a las 16 durante 1 hora",
    )

    assert resultado["ok"] is True
    assert "1. Elegir otra hora" in resultado["datos"]
    assert "2. Mover el evento existente" in resultado["datos"]
    assert "3. Cancelar el existente" in resultado["datos"]


def test_mueve_el_evento_existente_conservando_duracion():
    aplicacion, usuario = _entorno()
    _crear_gimnasio(aplicacion, usuario)

    aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "crea un evento dentista manana a las 16 durante 1 hora",
    )
    aplicacion.router.procesar(usuario.id, uuid4(), "2")
    resultado = aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "a las 18",
    )

    assert resultado["ok"] is True
    assert resultado["datos"]["comienza"] == "2026-11-13T18:00:00+01:00"
    assert resultado["datos"]["termina"] == "2026-11-13T19:00:00+01:00"


def test_cancela_el_existente_y_crea_el_nuevo():
    aplicacion, usuario = _entorno()
    _crear_gimnasio(aplicacion, usuario)

    aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "crea un evento dentista manana a las 16 durante 1 hora",
    )
    resultado = aplicacion.router.procesar(usuario.id, uuid4(), "3")

    assert resultado["ok"] is True
    assert resultado["datos"]["titulo"] == "dentista"


def test_ofrece_huecos_para_elegir_otra_hora():
    aplicacion, usuario = _entorno()
    _crear_gimnasio(aplicacion, usuario)

    aplicacion.router.procesar(
        usuario.id,
        uuid4(),
        "crea un evento dentista manana a las 16 durante 1 hora",
    )
    resultado = aplicacion.router.procesar(usuario.id, uuid4(), "1")

    assert resultado["ok"] is True
    assert "Horas libres cercanas" in resultado["datos"]
