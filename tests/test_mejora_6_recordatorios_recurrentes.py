from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domain.reminder import Recordatorio, RepeticionRecordatorio

MAD = ZoneInfo("Europe/Madrid")


def _recordatorio(repeticion=None):
    return Recordatorio(
        uuid4(),
        "Aviso",
        datetime(2026, 11, 16, 9, 0, tzinfo=MAD),
        repeticion=repeticion,
    )


def test_recordatorio_sin_repeticion_no_tiene_siguiente():
    r = _recordatorio()
    assert r.siguiente_ocurrencia() is None


def test_recordatorio_semanal_avanza_una_semana():
    r = _recordatorio(RepeticionRecordatorio.SEMANAL)
    assert r.siguiente_ocurrencia() == datetime(2026, 11, 23, 9, 0, tzinfo=MAD)


def test_recordatorio_mensual_avanza_un_mes():
    r = _recordatorio(RepeticionRecordatorio.MENSUAL)
    assert r.siguiente_ocurrencia() == datetime(2026, 12, 16, 9, 0, tzinfo=MAD)


def test_recordatorio_mensual_maneja_fin_de_mes():
    r = Recordatorio(
        uuid4(),
        "Aviso",
        datetime(2026, 1, 31, 9, 0, tzinfo=MAD),
        repeticion=RepeticionRecordatorio.MENSUAL,
    )
    assert r.siguiente_ocurrencia() == datetime(2026, 2, 28, 9, 0, tzinfo=MAD)


def test_recordatorio_mensual_cruza_ano():
    r = Recordatorio(
        uuid4(),
        "Aviso",
        datetime(2026, 12, 16, 9, 0, tzinfo=MAD),
        repeticion=RepeticionRecordatorio.MENSUAL,
    )
    assert r.siguiente_ocurrencia() == datetime(2027, 1, 16, 9, 0, tzinfo=MAD)
