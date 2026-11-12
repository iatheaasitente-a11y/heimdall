from datetime import UTC, date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.database.connection import crear_conexion
from app.database.esquema import aplicar_schema
from app.domain.habit import FrecuenciaHabito
from app.domain.user import Usuario
from app.repositories.sqlite_habitos import (
    RepositorioHabitosSQLite,
    RepositorioRegistrosHabitoSQLite,
)
from app.repositories.sqlite_usuarios import RepositorioUsuariosSQLite
from app.services.errores import (
    HabitoInactivo,
    HabitoNoEncontrado,
    RegistroNoEncontrado,
    UsuarioNoEncontrado,
)
from app.services.habitos import ServicioHabitos

MAD = ZoneInfo("Europe/Madrid")
AHORA = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


@pytest.fixture
def conexion():
    conexion = crear_conexion(":memory:")
    aplicar_schema(conexion)
    try:
        yield conexion
    finally:
        conexion.close()


@pytest.fixture
def entorno(conexion):
    usuarios = RepositorioUsuariosSQLite(conexion)
    habitos = RepositorioHabitosSQLite(conexion)
    registros = RepositorioRegistrosHabitoSQLite(conexion)
    usuario = Usuario(nombre="A")
    usuarios.guardar(usuario)
    servicio = ServicioHabitos(usuarios, habitos, registros, reloj=lambda: AHORA)
    return servicio, habitos, registros, usuario


@pytest.fixture
def otro_usuario(conexion):
    usuario = Usuario(nombre="B")
    RepositorioUsuariosSQLite(conexion).guardar(usuario)
    return usuario


def madrid(dia, hora, minuto=0):
    return datetime(2026, 10, dia, hora, minuto, tzinfo=MAD)


def test_crear_habito_guarda_y_recorta_los_textos(entorno):
    servicio, repo, _, u = entorno
    h = servicio.crear_habito(
        u.id, "  Beber agua ", FrecuenciaHabito.DIARIA, 2, " litros ", descripcion=" Dos al día "
    )
    assert (h.nombre, h.unidad, h.descripcion) == ("Beber agua", "litros", "Dos al día")
    assert h.objetivo == 2
    assert h.activo
    assert repo.obtener(h.id) == h


def test_crear_habito_tiene_valores_por_defecto(entorno):
    servicio, _, _, u = entorno
    h = servicio.crear_habito(u.id, "Meditar")
    assert h.frecuencia == FrecuenciaHabito.DIARIA
    assert (h.objetivo, h.unidad, h.descripcion) == (1.0, "veces", None)


def test_crear_habito_acepta_la_frecuencia_como_texto(entorno):
    servicio, _, _, u = entorno
    assert servicio.crear_habito(u.id, "Correr", "semanal").frecuencia == FrecuenciaHabito.SEMANAL


def test_crear_habito_con_frecuencia_inexistente_lanza_error(entorno):
    servicio, repo, _, u = entorno
    with pytest.raises(ValueError):
        servicio.crear_habito(u.id, "X", "cada rato")
    assert repo.listar_por_usuario(u.id) == []


def test_crear_habito_con_objetivo_no_positivo_lanza_error(entorno):
    servicio, repo, _, u = entorno
    with pytest.raises(ValueError):
        servicio.crear_habito(u.id, "X", objetivo=0)
    assert repo.listar_por_usuario(u.id) == []


def test_crear_habito_rechaza_nombre_vacio(entorno):
    servicio, repo, _, u = entorno
    with pytest.raises(ValidationError):
        servicio.crear_habito(u.id, "   ")
    assert repo.listar_por_usuario(u.id) == []


def test_crear_habito_de_usuario_inexistente_lanza_error(entorno):
    servicio, _, _, _ = entorno
    with pytest.raises(UsuarioNoEncontrado):
        servicio.crear_habito(uuid4(), "X")


def test_listar_habitos_ordena_por_nombre_y_filtra_activos(entorno):
    servicio, _, _, u = entorno
    servicio.crear_habito(u.id, "Zumba")
    viejo = servicio.crear_habito(u.id, "Ajedrez")
    servicio.desactivar_habito(u.id, viejo.id)
    assert [h.nombre for h in servicio.listar_habitos(u.id)] == ["Ajedrez", "Zumba"]
    assert [h.nombre for h in servicio.listar_habitos(u.id, solo_activos=True)] == ["Zumba"]


def test_listar_habitos_de_usuario_inexistente_lanza_error(entorno):
    servicio, _, _, _ = entorno
    with pytest.raises(UsuarioNoEncontrado):
        servicio.listar_habitos(uuid4())


def test_obtener_habito_inexistente_lanza_error(entorno):
    servicio, _, _, u = entorno
    with pytest.raises(HabitoNoEncontrado):
        servicio.obtener_habito(u.id, uuid4())


def test_desactivar_habito_se_guarda(entorno):
    servicio, repo, _, u = entorno
    h = servicio.crear_habito(u.id, "Leer")
    servicio.desactivar_habito(u.id, h.id)
    assert not repo.obtener(h.id).activo


def test_registrar_progreso_usa_el_reloj_por_defecto(entorno):
    servicio, _, repo, u = entorno
    h = servicio.crear_habito(u.id, "Leer")
    r = servicio.registrar_progreso(u.id, h.id, 1, notas="  Capítulo 3 ")
    assert r.fecha == AHORA
    assert r.notas == "Capítulo 3"
    assert repo.obtener(r.id) == r


def test_las_notas_vacias_se_guardan_como_ninguna(entorno):
    servicio, _, _, u = entorno
    h = servicio.crear_habito(u.id, "Leer")
    assert servicio.registrar_progreso(u.id, h.id, 1, notas="   ").notas is None


def test_completado_se_calcula_con_lo_acumulado_del_dia(entorno):
    servicio, _, _, u = entorno
    h = servicio.crear_habito(u.id, "Beber agua", objetivo=2, unidad="litros")
    primero = servicio.registrar_progreso(u.id, h.id, 1, madrid(23, 9))
    segundo = servicio.registrar_progreso(u.id, h.id, 1, madrid(23, 15))
    otro_dia = servicio.registrar_progreso(u.id, h.id, 1, madrid(22, 15))
    assert (primero.completado, segundo.completado, otro_dia.completado) == (False, True, False)


def test_registrar_progreso_rechaza_valor_negativo_y_no_guarda(entorno):
    servicio, _, repo, u = entorno
    h = servicio.crear_habito(u.id, "Leer")
    with pytest.raises(ValidationError):
        servicio.registrar_progreso(u.id, h.id, -1)
    assert repo.listar_por_habito(h.id) == []


def test_registrar_progreso_rechaza_fecha_sin_zona(entorno):
    servicio, _, repo, u = entorno
    h = servicio.crear_habito(u.id, "Leer")
    with pytest.raises(ValidationError):
        servicio.registrar_progreso(u.id, h.id, 1, datetime(2026, 10, 23, 9, 0))
    assert repo.listar_por_habito(h.id) == []


def test_no_se_registra_progreso_en_un_habito_desactivado(entorno):
    servicio, _, repo, u = entorno
    h = servicio.crear_habito(u.id, "Leer")
    servicio.desactivar_habito(u.id, h.id)
    with pytest.raises(HabitoInactivo):
        servicio.registrar_progreso(u.id, h.id, 1)
    assert repo.listar_por_habito(h.id) == []


def test_registrar_progreso_en_habito_inexistente_lanza_error(entorno):
    servicio, _, _, u = entorno
    with pytest.raises(HabitoNoEncontrado):
        servicio.registrar_progreso(u.id, uuid4(), 1)


def test_progreso_del_dia_usa_la_zona_del_usuario(entorno):
    servicio, _, _, u = entorno
    h = servicio.crear_habito(u.id, "Beber agua", objetivo=2, unidad="litros")
    servicio.registrar_progreso(u.id, h.id, 5, madrid(22, 23, 30))
    servicio.registrar_progreso(u.id, h.id, 1, madrid(23, 0, 30))
    servicio.registrar_progreso(u.id, h.id, 0.5, madrid(23, 18))
    assert servicio.progreso_del_dia(u.id, h.id, date(2026, 10, 23)) == 1.5
    assert servicio.progreso_del_dia(u.id, h.id) == 1.5
    assert servicio.progreso_del_dia(u.id, h.id, date(2026, 10, 22)) == 5


def test_la_racha_cuenta_dias_seguidos_hasta_hoy(entorno):
    servicio, _, _, u = entorno
    h = servicio.crear_habito(u.id, "Meditar")
    for dia in (21, 22, 23):
        servicio.registrar_progreso(u.id, h.id, 1, madrid(dia, 9))
    assert servicio.racha(u.id, h.id) == 3
    assert servicio.racha(u.id, h.id, hoy=date(2026, 10, 23)) == 3


def test_la_racha_no_se_rompe_hasta_que_acaba_el_dia(entorno):
    servicio, _, _, u = entorno
    h = servicio.crear_habito(u.id, "Meditar")
    for dia in (21, 22):
        servicio.registrar_progreso(u.id, h.id, 1, madrid(dia, 9))
    assert servicio.racha(u.id, h.id) == 2


def test_un_dia_sin_cumplir_corta_la_racha(entorno):
    servicio, _, _, u = entorno
    h = servicio.crear_habito(u.id, "Meditar")
    for dia in (20, 21, 23):
        servicio.registrar_progreso(u.id, h.id, 1, madrid(dia, 9))
    assert servicio.racha(u.id, h.id) == 1


def test_la_racha_solo_se_calcula_en_habitos_diarios(entorno):
    servicio, _, _, u = entorno
    h = servicio.crear_habito(u.id, "Correr", FrecuenciaHabito.SEMANAL)
    with pytest.raises(ValueError):
        servicio.racha(u.id, h.id)


def test_listar_registros_va_del_mas_antiguo_al_mas_reciente(entorno):
    servicio, _, _, u = entorno
    h = servicio.crear_habito(u.id, "Leer")
    tarde = servicio.registrar_progreso(u.id, h.id, 1, madrid(23, 18))
    pronto = servicio.registrar_progreso(u.id, h.id, 1, madrid(23, 8))
    assert [r.id for r in servicio.listar_registros(u.id, h.id)] == [pronto.id, tarde.id]


def test_eliminar_registro_lo_borra(entorno):
    servicio, _, repo, u = entorno
    h = servicio.crear_habito(u.id, "Leer")
    r = servicio.registrar_progreso(u.id, h.id, 1)
    servicio.eliminar_registro(u.id, h.id, r.id)
    assert repo.obtener(r.id) is None


def test_eliminar_un_registro_inexistente_lanza_error(entorno):
    servicio, _, _, u = entorno
    h = servicio.crear_habito(u.id, "Leer")
    with pytest.raises(RegistroNoEncontrado):
        servicio.eliminar_registro(u.id, h.id, uuid4())


def test_no_se_borra_un_registro_con_el_habito_equivocado(entorno):
    servicio, _, repo, u = entorno
    leer = servicio.crear_habito(u.id, "Leer")
    correr = servicio.crear_habito(u.id, "Correr")
    r = servicio.registrar_progreso(u.id, leer.id, 1)
    with pytest.raises(RegistroNoEncontrado):
        servicio.eliminar_registro(u.id, correr.id, r.id)
    assert repo.obtener(r.id) is not None


def test_un_usuario_no_ve_ni_toca_los_habitos_de_otro(entorno, otro_usuario):
    servicio, repo, registros, u = entorno
    h = servicio.crear_habito(u.id, "Privado")
    r = servicio.registrar_progreso(u.id, h.id, 1)
    ajeno = otro_usuario.id
    with pytest.raises(HabitoNoEncontrado):
        servicio.obtener_habito(ajeno, h.id)
    with pytest.raises(HabitoNoEncontrado):
        servicio.desactivar_habito(ajeno, h.id)
    with pytest.raises(HabitoNoEncontrado):
        servicio.registrar_progreso(ajeno, h.id, 1)
    with pytest.raises(HabitoNoEncontrado):
        servicio.listar_registros(ajeno, h.id)
    with pytest.raises(HabitoNoEncontrado):
        servicio.eliminar_registro(ajeno, h.id, r.id)
    with pytest.raises(HabitoNoEncontrado):
        servicio.progreso_del_dia(ajeno, h.id)
    with pytest.raises(HabitoNoEncontrado):
        servicio.racha(ajeno, h.id)
    assert repo.obtener(h.id).activo
    assert registros.obtener(r.id) is not None
    assert servicio.listar_habitos(ajeno) == []