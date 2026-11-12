import math
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.tools.esquemas import (
    ActualizarProgresoObjetivo,
    CrearEvento,
    CrearHabito,
    CrearObjetivo,
    IdentificadorEvento,
    IdentificadorRecordatorio,
    ProgramarRecordatorio,
    RegistrarProgresoHabito,
)


AHORA = datetime(2026, 11, 12, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    ("esquema", "argumentos", "campo"),
    [
        (
            CrearEvento,
            {"titulo": "x" * 501, "comienza": AHORA, "termina": AHORA},
            "titulo",
        ),
        (
            CrearEvento,
            {
                "titulo": "x",
                "comienza": AHORA,
                "termina": AHORA,
                "descripcion": "x" * 501,
            },
            "descripcion",
        ),
        (
            CrearEvento,
            {
                "titulo": "x",
                "comienza": AHORA,
                "termina": AHORA,
                "ubicacion": "x" * 501,
            },
            "ubicacion",
        ),
        (IdentificadorEvento, {"titulo": "x" * 501}, "titulo"),
        (CrearHabito, {"nombre": "x" * 501}, "nombre"),
        (RegistrarProgresoHabito, {"nombre": "x" * 501, "valor": 1}, "nombre"),
        (
            RegistrarProgresoHabito,
            {
                "habito_id": "00000000-0000-0000-0000-000000000001",
                "valor": 1,
                "notas": "x" * 501,
            },
            "notas",
        ),
        (CrearObjetivo, {"nombre": "x" * 501}, "nombre"),
        (CrearObjetivo, {"nombre": "x", "descripcion": "x" * 501}, "descripcion"),
        (ActualizarProgresoObjetivo, {"nombre": "x" * 501, "progreso": 1}, "nombre"),
        (IdentificadorRecordatorio, {"mensaje": "x" * 501}, "mensaje"),
        (ProgramarRecordatorio, {"mensaje": "x" * 501, "cuando": AHORA}, "mensaje"),
    ],
)
def test_esquemas_limitan_los_textos_a_500_caracteres(esquema, argumentos, campo):
    with pytest.raises(ValidationError, match=campo):
        esquema.model_validate(argumentos)


@pytest.mark.parametrize(
    ("esquema", "argumentos", "campo"),
    [
        (CrearHabito, {"nombre": "Leer", "objetivo": math.nan}, "objetivo"),
        (
            RegistrarProgresoHabito,
            {
                "habito_id": "00000000-0000-0000-0000-000000000001",
                "valor": math.inf,
            },
            "valor",
        ),
        (
            ActualizarProgresoObjetivo,
            {"nombre": "Estudiar", "progreso": -math.inf},
            "progreso",
        ),
    ],
)
def test_esquemas_rechazan_floats_no_finitos(esquema, argumentos, campo):
    with pytest.raises(ValidationError, match=campo):
        esquema.model_validate(argumentos)
