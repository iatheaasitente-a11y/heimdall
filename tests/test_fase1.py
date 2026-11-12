from app.telegram.conector import formatear_respuesta


def test_resumen_vacio_es_natural():
    salida = {
        "ok": True,
        "datos": {
            "dia": "2026-11-12",
            "eventos": [],
            "habitos_pendientes": [],
            "recordatorios": [],
        },
    }
    texto = formatear_respuesta(salida)
    assert "jueves 12 de noviembre de 2026" in texto
    assert "no tienes eventos ni recordatorios" in texto


def test_resumen_con_eventos():
    salida = {
        "ok": True,
        "datos": {
            "dia": "2026-11-12",
            "eventos": [
                {"titulo": "Dentista", "inicio": "10:00", "fin": "11:00"},
            ],
            "habitos_pendientes": [],
            "recordatorios": [],
        },
    }
    texto = formatear_respuesta(salida)
    assert "Dentista" in texto
    assert "10:00 a 11:00" in texto
