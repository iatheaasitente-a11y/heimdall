from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domain.schedule import Evento, Repeticion

MAD = ZoneInfo("Europe/Madrid")


def _evento(repeticion=None):
    return Evento(
        uuid4(),
        "Reunión",
        datetime(2026, 11, 16, 15, 0, tzinfo=MAD),
        datetime(2026, 11, 16, 16, 0, tzinfo=MAD),
        repeticion=repeticion,
    )


def test_evento_sin_repeticion_no_tiene_siguiente_ocurrencia():
    evento = _evento()
    assert evento.siguiente_ocurrencia(datetime(2026, 11, 16, tzinfo=MAD)) is None


def test_repeticion_semanal_avanza_una_semana():
    evento = _evento(Repeticion.SEMANAL)
    siguiente = evento.siguiente_ocurrencia(datetime(2026, 11, 16, tzinfo=MAD))
    assert siguiente == datetime(2026, 11, 23, 15, 0, tzinfo=MAD)


def test_repeticion_mensual_avanza_un_mes():
    evento = _evento(Repeticion.MENSUAL)
    siguiente = evento.siguiente_ocurrencia(datetime(2026, 11, 16, tzinfo=MAD))
    assert siguiente == datetime(2026, 12, 16, 15, 0, tzinfo=MAD)


def test_repeticion_mensual_maneja_fin_de_mes():
    evento = Evento(
        uuid4(),
        "Reunión",
        datetime(2026, 1, 31, 15, 0, tzinfo=MAD),
        datetime(2026, 1, 31, 16, 0, tzinfo=MAD),
        repeticion=Repeticion.MENSUAL,
    )
    siguiente = evento.siguiente_ocurrencia(datetime(2026, 1, 31, tzinfo=MAD))
    assert siguiente == datetime(2026, 2, 28, 15, 0, tzinfo=MAD)


def test_repeticion_mensual_cruza_ano():
    evento = Evento(
        uuid4(),
        "Reunión",
        datetime(2026, 12, 16, 15, 0, tzinfo=MAD),
        datetime(2026, 12, 16, 16, 0, tzinfo=MAD),
        repeticion=Repeticion.MENSUAL,
    )
    siguiente = evento.siguiente_ocurrencia(datetime(2026, 12, 16, tzinfo=MAD))
    assert siguiente == datetime(2027, 1, 16, 15, 0, tzinfo=MAD)
