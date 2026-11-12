from uuid import uuid4

import pytest

from app.domain.nba.falsa import FuenteNBAFalsa
from app.domain.nba.fuente import FuenteNBA
from app.tools.nba import herramienta_nba


def test_fuente_falsa_satisface_el_contrato_y_responde_sin_red():
    fuente: FuenteNBA = FuenteNBAFalsa(
        {"¿Cuándo juega Boston?": "Boston juega mañana."}
    )

    assert fuente.consultar("¿Cuándo juega Boston?") == "Boston juega mañana."


def test_herramienta_consulta_la_fuente_falsa():
    herramienta = herramienta_nba(
        FuenteNBAFalsa({"Lakers": "Próximo partido: Lakers contra Celtics."})
    )

    resultado = herramienta.ejecutar(uuid4(), {"consulta": "Lakers"})

    assert resultado == {
        "ok": True,
        "datos": "Próximo partido: Lakers contra Celtics.",
    }


def test_herramienta_convierte_falta_de_datos_en_error():
    herramienta = herramienta_nba(FuenteNBAFalsa({}))

    resultado = herramienta.ejecutar(uuid4(), {"consulta": "equipo desconocido"})

    assert resultado["ok"] is False
    assert "equipo desconocido" in resultado["error"]


def test_esquema_de_consulta_nba_rechaza_consulta_vacia():
    resultado = herramienta_nba(FuenteNBAFalsa({})).ejecutar(uuid4(), {"consulta": ""})

    assert resultado["ok"] is False
    assert "consulta" in resultado["error"]


def test_fuente_falsa_rechaza_consulta_sin_respuesta():
    with pytest.raises(ValueError, match="No hay datos NBA"):
        FuenteNBAFalsa({}).consultar("no disponible")
