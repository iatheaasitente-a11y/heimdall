from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain.lenguaje_fechas import (
    decir_duracion,
    decir_fecha,
    decir_hora,
    resolver_fecha,
    resolver_fecha_hora,
    resolver_hora,
)


MADRID = ZoneInfo("Europe/Madrid")
AHORA = datetime(2026, 11, 12, 10, 0, tzinfo=MADRID)


@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("hoy", date(2026, 11, 12)),
        ("mañana", date(2026, 11, 13)),
        ("pasado mañana", date(2026, 11, 14)),
        ("esta tarde", date(2026, 11, 12)),
        ("esta noche", date(2026, 11, 12)),
        ("por la mañana", None),
        ("jueves", date(2026, 11, 12)),
        ("el próximo jueves", date(2026, 11, 19)),
        ("viernes", date(2026, 11, 13)),
        ("el 15", date(2026, 11, 15)),
        ("el 10", date(2026, 12, 10)),
        ("el 15 de octubre", date(2027, 10, 15)),
        ("el 15 de diciembre", date(2026, 12, 15)),
        ("2026-11-15", date(2026, 11, 15)),
    ],
)
def test_resolver_fecha(texto, esperada):
    assert resolver_fecha(texto, AHORA) == esperada


@pytest.mark.parametrize("texto", ["ayer", "anteayer", "el viernes pasado", "en algún momento"])
def test_resolver_fecha_no_inventa_fechas_pasadas_o_ausentes(texto):
    assert resolver_fecha(texto, AHORA) is None


@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("ayer", date(2026, 11, 11)),
        ("anteayer", date(2026, 11, 10)),
    ],
)
def test_resolver_fecha_permite_pasado_si_se_solicita(texto, esperada):
    assert resolver_fecha(texto, AHORA, permitir_pasado=True) == esperada


def test_resolver_fecha_usa_la_fecha_local_de_la_zona_inyectada():
    ahora = datetime(2026, 11, 12, 0, 30, tzinfo=UTC).astimezone(MADRID)

    assert resolver_fecha("hoy", ahora) == date(2026, 11, 12)


def test_resolver_fecha_rechaza_datetime_sin_zona():
    with pytest.raises(ValueError, match="zona horaria"):
        resolver_fecha("mañana", datetime(2026, 11, 12, 10))


@pytest.mark.parametrize(
    ("texto", "esperada", "acotada", "franja"),
    [
        ("a las cinco", time(5), False, None),
        ("a las 5", time(5), False, None),
        ("a la una", time(1), False, None),
        ("a las 12", time(12), False, None),
        ("a las 17:30", time(17, 30), True, None),
        ("a las cinco de la mañana", time(5), True, "mañana"),
        ("a las cinco de la tarde", time(17), True, "tarde"),
        ("a las cinco de la noche", time(17), True, "noche"),
        ("a las doce de la noche", time(0), True, "noche"),
        ("a las doce del mediodía", time(12), True, "mediodía"),
        ("a las cinco y media de la tarde", time(17, 30), True, "tarde"),
        ("a las cinco y cuarto", time(5, 15), False, None),
        ("a las seis menos cuarto", time(5, 45), False, None),
        ("a las 13", time(13), True, None),
    ],
)
def test_resolver_hora(texto, esperada, acotada, franja):
    resultado = resolver_hora(texto)

    assert resultado is not None
    assert resultado.hora == esperada
    assert resultado.acotada is acotada
    assert resultado.franja == franja


@pytest.mark.parametrize("texto", ["a media tarde", "cinco", ""])
def test_resolver_hora_devuelve_none_si_no_hay_hora(texto):
    assert resolver_hora(texto) is None


def test_resolver_hora_conserva_la_ultima_franja_mencionada():
    resultado = resolver_hora("por la mañana, a las cinco de la tarde")

    assert resultado == type(resultado)(time(17), True, "tarde")


def test_resolver_fecha_hora_devuelve_none_si_no_hay_fecha():
    assert resolver_fecha_hora("a las cinco", AHORA) is None


def test_resolver_fecha_hora_marca_la_hora_sin_franja_como_no_acotada():
    resultado = resolver_fecha_hora("mañana a las cinco reunión", AHORA)

    assert resultado is not None
    assert resultado.fecha == date(2026, 11, 13)
    assert resultado.hora == time(5)
    assert resultado.hora_acotada is False


def test_resolver_fecha_hora_aplica_la_ultima_franja():
    resultado = resolver_fecha_hora(
        "mañana por la mañana a las cinco de la tarde",
        AHORA,
    )

    assert resultado is not None
    assert resultado.hora == time(17)
    assert resultado.franja == "tarde"


def test_resolver_fecha_hora_no_asume_una_hora():
    resultado = resolver_fecha_hora("pasado mañana", AHORA)

    assert resultado is not None
    assert resultado.hora is None
    assert resultado.hora_acotada is False


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (date(2026, 11, 12), "jueves, 12 de noviembre de 2026"),
        (date(2026, 1, 1), "jueves, 1 de enero de 2026"),
    ],
)
def test_decir_fecha(valor, esperado):
    assert decir_fecha(valor) == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (time(5), "las cinco de la mañana"),
        (time(12), "las doce de la tarde"),
        (time(17, 30), "las cinco y treinta de la tarde"),
        (time(23, 15), "las once y quince de la noche"),
    ],
)
def test_decir_hora(valor, esperado):
    assert decir_hora(valor) == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (timedelta(0), "cero segundos"),
        (timedelta(seconds=1), "un segundo"),
        (timedelta(minutes=1), "un minuto"),
        (timedelta(minutes=2), "dos minutos"),
        (timedelta(hours=1), "una hora"),
        (timedelta(hours=2, minutes=5), "dos horas y cinco minutos"),
        (timedelta(days=1, seconds=2), "veinticuatro horas y dos segundos"),
    ],
)
def test_decir_duracion(valor, esperado):
    assert decir_duracion(valor) == esperado


def test_decir_duracion_rechaza_valores_negativos():
    with pytest.raises(ValueError, match="negativa"):
        decir_duracion(timedelta(seconds=-1))
