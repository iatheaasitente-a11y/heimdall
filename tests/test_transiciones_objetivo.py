from uuid import uuid4

import pytest

from app.domain.errores import TransicionNoPermitida
from app.domain.goal import EstadoObjetivo, Objetivo


def un_objetivo(estado=EstadoObjetivo.ACTIVO, progreso=0):
    return Objetivo(uuid4(), "Meta", estado=estado, progreso=progreso)


@pytest.mark.parametrize(
    "accion,estado",
    [
        ("pausar", EstadoObjetivo.PAUSADO),
        ("reanudar", EstadoObjetivo.ACTIVO),
        ("cancelar", EstadoObjetivo.CANCELADO),
    ],
)
def test_transiciones_validas(accion, estado):
    objetivo = un_objetivo(
        EstadoObjetivo.PAUSADO if accion == "reanudar" else EstadoObjetivo.ACTIVO
    )
    getattr(objetivo, accion)()
    assert objetivo.estado == estado


@pytest.mark.parametrize(
    "accion,estado",
    [
        ("pausar", EstadoObjetivo.COMPLETADO),
        ("pausar", EstadoObjetivo.PAUSADO),
        ("pausar", EstadoObjetivo.CANCELADO),
        ("reanudar", EstadoObjetivo.ACTIVO),
        ("reanudar", EstadoObjetivo.COMPLETADO),
        ("reanudar", EstadoObjetivo.CANCELADO),
        ("cancelar", EstadoObjetivo.COMPLETADO),
        ("cancelar", EstadoObjetivo.CANCELADO),
    ],
)
def test_transiciones_invalidas_no_cambian_el_estado(accion, estado):
    objetivo = un_objetivo(estado)
    with pytest.raises(TransicionNoPermitida):
        getattr(objetivo, accion)()
    assert objetivo.estado == estado


@pytest.mark.parametrize("estado", list(EstadoObjetivo))
def test_restablecer_desde_cualquier_estado_conserva_el_progreso(estado):
    objetivo = un_objetivo(estado, progreso=42)
    objetivo.restablecer()
    assert objetivo.estado == EstadoObjetivo.ACTIVO
    assert objetivo.progreso == 42


def test_el_error_de_transicion_contiene_los_estados():
    objetivo = un_objetivo(EstadoObjetivo.COMPLETADO)
    with pytest.raises(TransicionNoPermitida) as info:
        objetivo.cancelar()
    assert info.value.actual == EstadoObjetivo.COMPLETADO
    assert info.value.destino == EstadoObjetivo.CANCELADO


@pytest.mark.parametrize("progreso", [0, 25, 99.5, 100])
def test_actualizar_progreso_conserva_su_comportamiento(progreso):
    objetivo = un_objetivo()
    objetivo.actualizar_progreso(progreso)
    assert objetivo.progreso == progreso
    assert objetivo.estado == (
        EstadoObjetivo.COMPLETADO if progreso == 100 else EstadoObjetivo.ACTIVO
    )


@pytest.mark.parametrize("progreso", [-1, 100.1])
def test_progreso_fuera_de_rango_no_modifica_el_objetivo(progreso):
    objetivo = un_objetivo(progreso=30)
    with pytest.raises(ValueError):
        objetivo.actualizar_progreso(progreso)
    assert (objetivo.progreso, objetivo.estado) == (30, EstadoObjetivo.ACTIVO)
