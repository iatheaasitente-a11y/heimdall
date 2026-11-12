from datetime import UTC, date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.database.connection import crear_conexion
from app.database.esquema import aplicar_schema
from app.domain.goal import EstadoObjetivo, Objetivo
from app.domain.user import Usuario
from app.repositories.sqlite_objetivos import RepositorioObjetivosSQLite
from app.repositories.sqlite_usuarios import RepositorioUsuariosSQLite
from app.services.errores import (
    CambioDeEstadoNoPermitido,
    FechaLimiteEnElPasado,
    ObjetivoNoActivo,
    ObjetivoNoEncontrado,
    UsuarioNoEncontrado,
)
from app.services.objetivos import ServicioObjetivos

AHORA = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
HOY = date(2026, 10, 23)


@pytest.fixture
def entorno():
    conexion = crear_conexion(":memory:")
    aplicar_schema(conexion)
    try:
        usuarios = RepositorioUsuariosSQLite(conexion)
        objetivos = RepositorioObjetivosSQLite(conexion)
        usuario = Usuario(nombre="A")
        usuarios.guardar(usuario)
        servicio = ServicioObjetivos(usuarios, objetivos, reloj=lambda: AHORA)
        yield servicio, usuarios, objetivos, usuario
    finally:
        conexion.close()


@pytest.fixture
def otro_usuario(entorno):
    _, usuarios, _, _ = entorno
    usuario = Usuario(nombre="B")
    usuarios.guardar(usuario)
    return usuario


def test_crear_objetivo_guarda_y_recorta_textos(entorno):
    servicio, _, repositorio, usuario = entorno
    objetivo = servicio.crear_objetivo(
        usuario.id, "  Aprender Python ", " Mejorar con proyectos  ", date(2026, 12, 1)
    )
    assert (objetivo.nombre, objetivo.descripcion) == ("Aprender Python", "Mejorar con proyectos")
    assert repositorio.obtener(objetivo.id) == objetivo


def test_crear_objetivo_con_descripcion_vacia_la_normaliza(entorno):
    servicio, _, _, usuario = entorno
    assert servicio.crear_objetivo(usuario.id, "Meta", "  ").descripcion is None


def test_crear_objetivo_rechaza_nombre_vacio(entorno):
    servicio, _, repositorio, usuario = entorno
    with pytest.raises(ValidationError):
        servicio.crear_objetivo(usuario.id, "   ")
    assert repositorio.listar_por_usuario(usuario.id) == []


def test_crear_objetivo_de_usuario_inexistente_falla(entorno):
    servicio, _, _, _ = entorno
    with pytest.raises(UsuarioNoEncontrado):
        servicio.crear_objetivo(uuid4(), "Meta")


@pytest.mark.parametrize("fecha", [date(2026, 10, 22), date(2020, 1, 1)])
def test_crear_objetivo_rechaza_fecha_pasada_sin_guardar(entorno, fecha):
    servicio, _, repositorio, usuario = entorno
    with pytest.raises(FechaLimiteEnElPasado) as info:
        servicio.crear_objetivo(usuario.id, "Meta", fecha_limite=fecha)
    assert info.value.fecha_limite == fecha
    assert repositorio.listar_por_usuario(usuario.id) == []


def test_crear_objetivo_acepta_fecha_de_hoy(entorno):
    servicio, _, _, usuario = entorno
    assert servicio.crear_objetivo(usuario.id, "Meta", fecha_limite=HOY).fecha_limite == HOY


def test_fecha_actual_se_calcula_en_zona_del_usuario(entorno):
    _, usuarios, objetivos, usuario = entorno
    # 22:30 UTC del día anterior ya es el día 23 en Madrid.
    servicio_utc = ServicioObjetivos(
        usuarios,
        objetivos,
        reloj=lambda: datetime(2026, 10, 22, 22, 30, tzinfo=UTC),
    )
    assert servicio_utc.crear_objetivo(usuario.id, "Hoy", fecha_limite=HOY).fecha_limite == HOY
    with pytest.raises(FechaLimiteEnElPasado):
        servicio_utc.crear_objetivo(usuario.id, "Ayer", fecha_limite=date(2026, 10, 22))


def test_obtener_objetivo_devuelve_el_guardado(entorno):
    servicio, _, _, usuario = entorno
    objetivo = servicio.crear_objetivo(usuario.id, "Meta")
    assert servicio.obtener_objetivo(usuario.id, objetivo.id) == objetivo


def test_obtener_objetivo_inexistente_falla(entorno):
    servicio, _, _, usuario = entorno
    with pytest.raises(ObjetivoNoEncontrado):
        servicio.obtener_objetivo(usuario.id, uuid4())


def test_listar_objetivos_de_usuario_inexistente_falla(entorno):
    servicio, _, _, _ = entorno
    with pytest.raises(UsuarioNoEncontrado):
        servicio.listar_objetivos(uuid4())


def test_listar_objetivos_ordena_por_fecha_y_sin_fecha_al_final(entorno):
    servicio, _, _, usuario = entorno
    servicio.crear_objetivo(usuario.id, "Sin fecha")
    servicio.crear_objetivo(usuario.id, "Lejano", fecha_limite=date(2027, 1, 1))
    servicio.crear_objetivo(usuario.id, "Cercano", fecha_limite=date(2026, 11, 1))
    assert [o.nombre for o in servicio.listar_objetivos(usuario.id)] == [
        "Cercano",
        "Lejano",
        "Sin fecha",
    ]


@pytest.mark.parametrize("estado", [EstadoObjetivo.PAUSADO, "pausado"])
def test_listar_objetivos_filtra_por_enum_o_texto(entorno, estado):
    servicio, _, _, usuario = entorno
    activo = servicio.crear_objetivo(usuario.id, "Activo")
    pausado = servicio.crear_objetivo(usuario.id, "Pausado")
    servicio.pausar_objetivo(usuario.id, pausado.id)
    assert [o.id for o in servicio.listar_objetivos(usuario.id, estado)] == [pausado.id]
    assert servicio.obtener_objetivo(usuario.id, activo.id).estado == EstadoObjetivo.ACTIVO


def test_listar_objetivos_rechaza_estado_desconocido(entorno):
    servicio, _, _, usuario = entorno
    with pytest.raises(ValueError):
        servicio.listar_objetivos(usuario.id, "desconocido")


def test_actualizar_progreso_guarda_el_cambio(entorno):
    servicio, _, repositorio, usuario = entorno
    objetivo = servicio.crear_objetivo(usuario.id, "Meta")
    actualizado = servicio.actualizar_progreso(usuario.id, objetivo.id, 40)
    assert actualizado.progreso == 40
    assert repositorio.obtener(objetivo.id).progreso == 40


def test_progreso_100_completa_y_conserva_el_objetivo(entorno):
    servicio, _, repositorio, usuario = entorno
    objetivo = servicio.crear_objetivo(usuario.id, "Meta")
    servicio.actualizar_progreso(usuario.id, objetivo.id, 100)
    guardado = servicio.obtener_objetivo(usuario.id, objetivo.id)
    assert guardado.estado == EstadoObjetivo.COMPLETADO
    assert guardado.progreso == 100
    assert repositorio.obtener(objetivo.id) == guardado


@pytest.mark.parametrize("progreso", [-1, 100.1])
def test_progreso_fuera_de_rango_no_modifica_ni_guarda(entorno, progreso):
    servicio, _, repositorio, usuario = entorno
    objetivo = servicio.crear_objetivo(usuario.id, "Meta")
    servicio.actualizar_progreso(usuario.id, objetivo.id, 30)
    with pytest.raises(ValueError):
        servicio.actualizar_progreso(usuario.id, objetivo.id, progreso)
    guardado = repositorio.obtener(objetivo.id)
    assert (guardado.progreso, guardado.estado) == (30, EstadoObjetivo.ACTIVO)


@pytest.mark.parametrize(
    "estado",
    [EstadoObjetivo.PAUSADO, EstadoObjetivo.COMPLETADO, EstadoObjetivo.CANCELADO],
)
def test_objetivo_no_activo_rechaza_progreso_y_se_conserva(entorno, estado):
    servicio, _, repositorio, usuario = entorno
    objetivo = Objetivo(usuario.id, "Cerrado", progreso=35, estado=estado)
    repositorio.guardar(objetivo)
    with pytest.raises(ObjetivoNoActivo, match="El objetivo «Cerrado» no está activo."):
        servicio.actualizar_progreso(usuario.id, objetivo.id, 70)
    guardado = repositorio.obtener(objetivo.id)
    assert (guardado.progreso, guardado.estado) == (35, estado)


def test_pausar_y_reanudar_guardan_transiciones(entorno):
    servicio, _, repositorio, usuario = entorno
    objetivo = servicio.crear_objetivo(usuario.id, "Meta")
    servicio.pausar_objetivo(usuario.id, objetivo.id)
    assert repositorio.obtener(objetivo.id).estado == EstadoObjetivo.PAUSADO
    servicio.reanudar_objetivo(usuario.id, objetivo.id)
    assert repositorio.obtener(objetivo.id).estado == EstadoObjetivo.ACTIVO


@pytest.mark.parametrize(
    "metodo,estado",
    [
        ("pausar_objetivo", EstadoObjetivo.PAUSADO),
        ("reanudar_objetivo", EstadoObjetivo.ACTIVO),
        ("cancelar_objetivo", EstadoObjetivo.COMPLETADO),
        ("cancelar_objetivo", EstadoObjetivo.CANCELADO),
    ],
)
def test_transicion_invalida_se_traduce_y_no_guarda(entorno, metodo, estado):
    servicio, _, repositorio, usuario = entorno
    objetivo = Objetivo(usuario.id, "Meta", estado=estado)
    repositorio.guardar(objetivo)
    with pytest.raises(CambioDeEstadoNoPermitido):
        getattr(servicio, metodo)(usuario.id, objetivo.id)
    assert repositorio.obtener(objetivo.id).estado == estado


@pytest.mark.parametrize("estado", [EstadoObjetivo.COMPLETADO, EstadoObjetivo.CANCELADO])
@pytest.mark.parametrize(
    "metodo",
    ["pausar_objetivo", "reanudar_objetivo", "cancelar_objetivo"],
)
def test_objetivo_cerrado_rechaza_todas_las_transiciones(entorno, metodo, estado):
    servicio, _, repositorio, usuario = entorno
    objetivo = Objetivo(usuario.id, "Cerrado", estado=estado)
    repositorio.guardar(objetivo)
    with pytest.raises(CambioDeEstadoNoPermitido):
        getattr(servicio, metodo)(usuario.id, objetivo.id)
    assert repositorio.obtener(objetivo.id).estado == estado


@pytest.mark.parametrize("estado", [EstadoObjetivo.ACTIVO, EstadoObjetivo.PAUSADO])
def test_cancelar_objetivo_activo_o_pausado(entorno, estado):
    servicio, _, repositorio, usuario = entorno
    objetivo = Objetivo(usuario.id, "Meta", estado=estado)
    repositorio.guardar(objetivo)
    servicio.cancelar_objetivo(usuario.id, objetivo.id)
    assert repositorio.obtener(objetivo.id).estado == EstadoObjetivo.CANCELADO


def test_dias_restantes_usa_hoy_en_zona_del_usuario(entorno):
    servicio, _, _, usuario = entorno
    objetivo = servicio.crear_objetivo(usuario.id, "Meta", fecha_limite=date(2026, 10, 25))
    assert servicio.dias_restantes(usuario.id, objetivo.id) == 2


@pytest.mark.parametrize(
    "fecha,esperado",
    [(date(2026, 10, 23), 0), (date(2026, 10, 22), -1), (None, None)],
)
def test_dias_restantes_con_fecha_de_referencia_o_sin_limite(
    entorno, fecha, esperado
):
    servicio, _, repositorio, usuario = entorno
    objetivo = Objetivo(usuario.id, "Meta", fecha_limite=fecha)
    repositorio.guardar(objetivo)
    assert servicio.dias_restantes(usuario.id, objetivo.id, hoy=HOY) == esperado


def test_dias_restantes_objetivo_ajeno_falla(entorno, otro_usuario):
    servicio, _, _, usuario = entorno
    objetivo = servicio.crear_objetivo(usuario.id, "Privado")
    with pytest.raises(ObjetivoNoEncontrado):
        servicio.dias_restantes(otro_usuario.id, objetivo.id)


def test_vencidos_solo_devuelve_activos_con_fecha_estrictamente_pasada(entorno):
    servicio, _, repositorio, usuario = entorno
    vencido = Objetivo(usuario.id, "Vencido", fecha_limite=date(2026, 10, 22))
    hoy = Objetivo(usuario.id, "Hoy", fecha_limite=HOY)
    futuro = Objetivo(usuario.id, "Futuro", fecha_limite=date(2026, 10, 24))
    pausado = Objetivo(
        usuario.id,
        "Pausado",
        fecha_limite=date(2026, 10, 22),
        estado=EstadoObjetivo.PAUSADO,
    )
    for objetivo in (vencido, hoy, futuro, pausado):
        repositorio.guardar(objetivo)
    assert [o.nombre for o in servicio.vencidos(usuario.id, hoy=HOY)] == ["Vencido"]


def test_vencidos_usa_reloj_y_repositorio_del_usuario(entorno, otro_usuario):
    servicio, _, repositorio, usuario = entorno
    vencido = Objetivo(usuario.id, "Vencido", fecha_limite=date(2026, 10, 22))
    repositorio.guardar(vencido)
    otro = Objetivo(otro_usuario.id, "Ajeno", fecha_limite=date(2026, 10, 22))
    repositorio.guardar(otro)
    assert servicio.vencidos(usuario.id) == [vencido]


def test_vencidos_de_usuario_inexistente_falla(entorno):
    servicio, _, _, _ = entorno
    with pytest.raises(UsuarioNoEncontrado):
        servicio.vencidos(uuid4())


@pytest.mark.parametrize(
    "metodo,args",
    [
        ("actualizar_progreso", (25,)),
        ("pausar_objetivo", ()),
        ("reanudar_objetivo", ()),
        ("cancelar_objetivo", ()),
        ("dias_restantes", ()),
    ],
)
def test_operaciones_rechazan_objetivo_de_otro_usuario(entorno, otro_usuario, metodo, args):
    servicio, _, _, usuario = entorno
    objetivo = servicio.crear_objetivo(usuario.id, "Privado")
    with pytest.raises(ObjetivoNoEncontrado):
        getattr(servicio, metodo)(otro_usuario.id, objetivo.id, *args)


def test_objetivo_cancelado_se_puede_consultar_y_listar(entorno):
    servicio, _, _, usuario = entorno
    objetivo = servicio.crear_objetivo(usuario.id, "Conservar")
    servicio.cancelar_objetivo(usuario.id, objetivo.id)
    guardado = servicio.obtener_objetivo(usuario.id, objetivo.id)
    assert guardado.estado == EstadoObjetivo.CANCELADO
    assert servicio.listar_objetivos(usuario.id, "cancelado") == [guardado]
