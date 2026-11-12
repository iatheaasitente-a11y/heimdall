import json
import sqlite3
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.database.connection import crear_conexion
from app.database.esquema import aplicar_schema
from app.domain.habit import FrecuenciaHabito
from app.domain.user import Usuario
from app.repositories.sqlite_eventos import RepositorioEventosSQLite
from app.repositories.sqlite_habitos import (
    RepositorioHabitosSQLite,
    RepositorioRegistrosHabitoSQLite,
)
from app.repositories.sqlite_objetivos import RepositorioObjetivosSQLite
from app.repositories.sqlite_recordatorios import RepositorioRecordatoriosSQLite
from app.repositories.sqlite_usuarios import RepositorioUsuariosSQLite
from app.services.agenda import ServicioAgenda
from app.services.errores import ErrorDeServicio, ErrorResolucionNombre
from app.services.habitos import ServicioHabitos
from app.services.objetivos import ServicioObjetivos
from app.services.recordatorios import ServicioRecordatorios
from app.services.usuarios import ServicioUsuarios
from app.tools.base import Herramienta
from app.tools.esquemas import Parametros
from app.tools.registro import RegistroHerramientas, registrar_herramientas

AHORA = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
DIA = date(2026, 10, 24)


@pytest.fixture
def entorno():
    conexion = crear_conexion(":memory:")
    aplicar_schema(conexion)
    try:
        usuarios_repo = RepositorioUsuariosSQLite(conexion)
        eventos_repo = RepositorioEventosSQLite(conexion)
        habitos_repo = RepositorioHabitosSQLite(conexion)
        registros_repo = RepositorioRegistrosHabitoSQLite(conexion)
        objetivos_repo = RepositorioObjetivosSQLite(conexion)
        recordatorios_repo = RepositorioRecordatoriosSQLite(conexion)
        usuario = Usuario(nombre="A")
        usuarios_repo.guardar(usuario)
        usuarios = ServicioUsuarios(usuarios_repo)
        agenda = ServicioAgenda(usuarios_repo, eventos_repo, recordatorios_repo)
        habitos = ServicioHabitos(
            usuarios_repo,
            habitos_repo,
            registros_repo,
            reloj=lambda: AHORA,
        )
        objetivos = ServicioObjetivos(
            usuarios_repo,
            objetivos_repo,
            reloj=lambda: AHORA,
        )
        recordatorios = ServicioRecordatorios(
            usuarios_repo,
            eventos_repo,
            recordatorios_repo,
            reloj=lambda: AHORA,
        )
        registro = registrar_herramientas(
            RegistroHerramientas(),
            usuarios,
            agenda,
            habitos,
            objetivos,
            recordatorios,
        )
        yield registro, usuario, usuarios, agenda, habitos, objetivos, recordatorios
    finally:
        conexion.close()


def herramienta(entorno, nombre):
    return entorno[0].obtener(nombre)


def test_catalogo_registra_todas_las_herramientas_iniciales(entorno):
    nombres = {item.nombre for item in entorno[0].listar()}
    assert len(nombres) == 25
    assert {
        "agenda_crear_evento",
        "habitos_listar",
        "habitos_registrar_progreso",
        "objetivos_reanudar",
        "recordatorios_listar",
        "recordatorios_pendientes_del_dia",
        "resumen_del_dia",
    } <= nombres
    assert "recordatorios_marcar_enviado" not in nombres
    assert "recordatorios_vencidos" not in nombres


def test_esquema_json_no_incluye_usuario_id(entorno):
    for item in entorno[0].listar():
        esquema = item.esquema_json()
        assert "usuario_id" not in esquema.get("properties", {})


def test_esquema_rechaza_usuario_id_en_argumentos_con_error_json(entorno):
    item = herramienta(entorno, "agenda_eventos_del_dia")
    resultado = item.ejecutar(
        entorno[1].id,
        {"dia": DIA, "usuario_id": str(uuid4())},
    )
    assert resultado["ok"] is False
    assert "usuario_id" in resultado["error"]


def test_herramienta_json_schema_deriva_del_modelo_pydantic():
    class ParametrosTexto(Parametros):
        texto: str

    item = Herramienta("eco", "Devuelve el texto.", ParametrosTexto, lambda _, args: args)
    esquema = item.esquema_json()
    assert esquema["properties"]["texto"]["type"] == "string"
    assert item.ejecutar(uuid4(), {"texto": "hola"}) == {
        "ok": True,
        "datos": {"texto": "hola"},
    }


def test_catalogo_rechaza_nombres_duplicados_y_no_existentes(entorno):
    registro = RegistroHerramientas()
    item = herramienta(entorno, "objetivos_listar")
    registro.registrar(item)
    with pytest.raises(ValueError):
        registro.registrar(item)
    with pytest.raises(KeyError):
        registro.obtener("inexistente")


def test_error_de_servicio_se_devuelve_como_error_json():
    def fallar(usuario_id, argumentos):
        del usuario_id, argumentos
        raise ErrorDeServicio("Error previsto.")

    item = Herramienta(
        "fallo",
        "Falla de forma prevista.",
        Parametros,
        fallar,
    )
    assert item.ejecutar(uuid4(), {}) == {
        "ok": False,
        "error": "Error previsto.",
    }


def test_valor_error_del_servicio_se_devuelve_como_error_json():
    def fallar(usuario_id, argumentos):
        del usuario_id, argumentos
        raise ValueError("Valor inválido.")

    item = Herramienta("fallo", "Falla con un valor inválido.", Parametros, fallar)
    assert item.ejecutar(uuid4(), {}) == {
        "ok": False,
        "error": "Valor inválido.",
    }


@pytest.mark.parametrize(
    "error",
    [sqlite3.OperationalError, OSError, TypeError],
)
def test_fallos_inesperados_de_herramienta_se_registran_y_devuelven_error(
    error,
    caplog,
):
    def fallar(usuario_id, argumentos):
        del usuario_id, argumentos
        raise error("detalle interno")

    item = Herramienta("fallo", "Falla de forma inesperada.", Parametros, fallar)

    resultado = item.ejecutar(uuid4(), {})

    assert resultado == {
        "ok": False,
        "error": "No se pudo completar la herramienta por un error interno.",
    }
    assert "Fallo inesperado al ejecutar la herramienta fallo." in caplog.text
    assert "detalle interno" in caplog.text


def test_error_al_serializar_herramienta_se_registra_y_devuelve_error(caplog):
    item = Herramienta(
        "fallo_serializacion",
        "Devuelve un objeto no serializable.",
        Parametros,
        lambda _usuario_id, _argumentos: object(),
    )

    resultado = item.ejecutar(uuid4(), {})

    assert resultado["ok"] is False
    assert "error interno" in resultado["error"]
    assert "Fallo inesperado al ejecutar la herramienta" in caplog.text


def test_nombre_en_blanco_se_devuelve_como_error_json(entorno):
    resultado = herramienta(entorno, "habitos_crear").ejecutar(
        entorno[1].id,
        {"nombre": "   "},
    )
    assert resultado["ok"] is False
    assert "nombre" in resultado["error"]


def test_progreso_fuera_de_rango_se_devuelve_como_error_json(entorno):
    resultado = herramienta(entorno, "objetivos_actualizar_progreso").ejecutar(
        entorno[1].id,
        {"objetivo_id": str(uuid4()), "progreso": 101},
    )
    assert resultado["ok"] is False
    assert "progreso" in resultado["error"]


def test_racha_de_habito_semanal_se_devuelve_como_error_json(entorno):
    usuario_id = entorno[1].id
    habito = herramienta(entorno, "habitos_crear").ejecutar(
        usuario_id,
        {"nombre": "Semanal", "frecuencia": FrecuenciaHabito.SEMANAL.value},
    )["datos"]
    resultado = herramienta(entorno, "habitos_racha").ejecutar(
        usuario_id,
        {"habito_id": habito["id"], "dia": "2026-10-23"},
    )
    assert resultado["ok"] is False
    assert "frecuencia diaria" in resultado["error"]


def test_crear_evento_delega_en_agenda_y_devuelve_json(entorno):
    item = herramienta(entorno, "agenda_crear_evento")
    resultado = item.ejecutar(
        entorno[1].id,
        {
            "titulo": "Reunión",
            "comienza": "2026-10-24T10:00:00+00:00",
            "termina": "2026-10-24T11:00:00+00:00",
        },
    )
    assert resultado["ok"] is True
    assert resultado["datos"]["titulo"] == "Reunión"
    assert json.loads(json.dumps(resultado))["datos"]["comienza"] == (
        "2026-10-24T10:00:00+00:00"
    )


def test_error_de_agenda_ajena_se_envuelve_sin_revelar_el_evento(entorno):
    resultado = herramienta(entorno, "agenda_cancelar_evento").ejecutar(
        uuid4(), {"evento_id": str(uuid4())}
    )
    assert resultado["ok"] is False
    assert resultado["error"].startswith("No existe el evento")


def test_completar_y_reprogramar_evento(entorno):
    agenda = entorno[3]
    evento = agenda.crear_evento(
        entorno[1].id,
        "Cita",
        datetime(2026, 10, 24, 10, tzinfo=UTC),
        datetime(2026, 10, 24, 11, tzinfo=UTC),
    )
    reprogramar = herramienta(entorno, "agenda_reprogramar_evento")
    cambiado = reprogramar.ejecutar(
        entorno[1].id,
        {
            "evento_id": str(evento.id),
            "comienza": "2026-10-24T12:00:00+00:00",
            "termina": "2026-10-24T13:00:00+00:00",
        },
    )
    assert cambiado["ok"] is True
    assert cambiado["datos"]["comienza"] == "2026-10-24T12:00:00+00:00"
    completado = herramienta(entorno, "agenda_completar_evento").ejecutar(
        entorno[1].id, {"evento_id": str(evento.id)}
    )
    assert completado["datos"]["estado"] == "completado"


def test_eventos_del_dia_usa_el_servicio_real(entorno):
    agenda = entorno[3]
    agenda.crear_evento(
        entorno[1].id,
        "Sábado",
        datetime(2026, 10, 24, 10, tzinfo=UTC),
        datetime(2026, 10, 24, 11, tzinfo=UTC),
    )
    resultado = herramienta(entorno, "agenda_eventos_del_dia").ejecutar(
        entorno[1].id, {"dia": DIA.isoformat()}
    )
    assert [evento["titulo"] for evento in resultado["datos"]] == ["Sábado"]


def test_herramientas_de_habitos_crean_registran_consultan_y_calculan_racha(entorno):
    usuario_id = entorno[1].id
    creado = herramienta(entorno, "habitos_crear").ejecutar(
        usuario_id,
        {"nombre": "Meditar", "frecuencia": FrecuenciaHabito.DIARIA.value},
    )
    habito_id = creado["datos"]["id"]
    registrado = herramienta(entorno, "habitos_registrar_progreso").ejecutar(
        usuario_id, {"habito_id": habito_id, "valor": 1}
    )
    assert registrado["datos"]["completado"] is True
    progreso = herramienta(entorno, "habitos_progreso_del_dia").ejecutar(
        usuario_id, {"habito_id": habito_id, "dia": "2026-10-23"}
    )
    assert progreso["datos"] == 1
    racha = herramienta(entorno, "habitos_racha").ejecutar(
        usuario_id, {"habito_id": habito_id, "dia": "2026-10-23"}
    )
    assert racha["datos"] == 1


def test_listar_habitos_y_recordatorios_usa_servicios_reales(entorno):
    usuario_id = entorno[1].id
    habitos = entorno[4]
    habito = habitos.crear_habito(usuario_id, "Leer")
    habitos.desactivar_habito(usuario_id, habito.id)
    activo = habitos.crear_habito(usuario_id, "Correr")
    entorno[6].programar(
        usuario_id,
        "Llamar a Marta",
        datetime(2026, 10, 24, 10, tzinfo=UTC),
    )

    lista_completa = herramienta(entorno, "habitos_listar").ejecutar(
        usuario_id, {}
    )
    solo_activos = herramienta(entorno, "habitos_listar").ejecutar(
        usuario_id, {"solo_activos": True}
    )
    recordatorios = herramienta(entorno, "recordatorios_listar").ejecutar(
        usuario_id, {}
    )

    assert {item["id"] for item in lista_completa["datos"]} == {
        str(habito.id),
        str(activo.id),
    }
    assert [item["id"] for item in solo_activos["datos"]] == [str(activo.id)]
    assert [item["mensaje"] for item in recordatorios["datos"]] == ["Llamar a Marta"]


def test_progreso_de_habito_se_resuelve_por_nombre_sin_tildes_y_mayusculas(entorno):
    usuario_id = entorno[1].id
    habito = entorno[4].crear_habito(usuario_id, "Café de Marta")

    resultado = herramienta(entorno, "habitos_registrar_progreso").ejecutar(
        usuario_id,
        {"nombre": "CAFE DE MARTA", "valor": 1},
    )

    assert resultado["ok"] is True
    assert resultado["datos"]["habito_id"] == str(habito.id)


def test_nombre_ambiguo_devuelve_candidatos_para_habitos(entorno):
    usuario_id = entorno[1].id
    primero = entorno[4].crear_habito(usuario_id, "Agua")
    segundo = entorno[4].crear_habito(usuario_id, "Água")

    resultado = herramienta(entorno, "habitos_progreso_del_dia").ejecutar(
        usuario_id,
        {"nombre": "AGUA"},
    )

    assert resultado["ok"] is False
    assert "Hay varios" in resultado["error"]
    assert {
        candidato["id"] for candidato in resultado["candidatos"]
    } == {str(primero.id), str(segundo.id)}


def test_error_de_resolucion_conserva_las_jerarquias_del_error():
    error = ErrorResolucionNombre("No hay coincidencia", [])

    assert isinstance(error, ErrorDeServicio)
    assert isinstance(error, ValueError)


def test_nombre_inexistente_devuelve_lista_de_candidatos_vacia(entorno):
    resultado = herramienta(entorno, "habitos_racha").ejecutar(
        entorno[1].id,
        {"nombre": "Leer"},
    )

    assert resultado["ok"] is False
    assert resultado["candidatos"] == []


def test_busqueda_por_nombre_es_exacta_y_limitada_al_usuario(entorno):
    otro = entorno[2].registrar("B")
    entorno[4].crear_habito(otro.id, "Leer")
    entorno[4].crear_habito(entorno[1].id, "Ana  María")

    parcial = herramienta(entorno, "habitos_progreso_del_dia").ejecutar(
        entorno[1].id,
        {"nombre": "lee"},
    )
    espacio_distinto = herramienta(entorno, "habitos_progreso_del_dia").ejecutar(
        entorno[1].id,
        {"nombre": "Ana María"},
    )

    assert parcial["ok"] is False
    assert parcial["candidatos"] == []
    assert espacio_distinto["ok"] is False
    assert espacio_distinto["candidatos"] == []


def test_objetivo_se_puede_actualizar_y_cancelar_por_nombre(entorno):
    usuario_id = entorno[1].id
    objetivo = entorno[5].crear_objetivo(usuario_id, "Correr 5 km")
    actualizar = herramienta(entorno, "objetivos_actualizar_progreso").ejecutar(
        usuario_id,
        {"nombre": "CORRER 5 KM", "progreso": 40},
    )
    cancelar = herramienta(entorno, "objetivos_cancelar").ejecutar(
        usuario_id,
        {"nombre": "Correr 5 km"},
    )

    assert actualizar["datos"]["id"] == str(objetivo.id)
    assert actualizar["datos"]["progreso"] == 40
    assert cancelar["datos"]["estado"] == "cancelado"


def test_evento_se_puede_completar_y_reprogramar_por_titulo(entorno):
    usuario_id = entorno[1].id
    evento = entorno[3].crear_evento(
        usuario_id,
        "Reunión importante",
        datetime(2026, 10, 24, 10, tzinfo=UTC),
        datetime(2026, 10, 24, 11, tzinfo=UTC),
    )
    reprogramado = herramienta(entorno, "agenda_reprogramar_evento").ejecutar(
        usuario_id,
        {
            "titulo": "REUNIÓN IMPORTANTE",
            "comienza": "2026-10-24T12:00:00+00:00",
            "termina": "2026-10-24T13:00:00+00:00",
        },
    )
    completado = herramienta(entorno, "agenda_completar_evento").ejecutar(
        usuario_id,
        {"titulo": "Reunión importante"},
    )

    assert reprogramado["datos"]["id"] == str(evento.id)
    assert completado["datos"]["estado"] == "completado"


def test_titulo_ambiguo_de_evento_devuelve_candidatos(entorno):
    usuario_id = entorno[1].id
    primero = entorno[3].crear_evento(
        usuario_id,
        "Cita",
        datetime(2026, 10, 24, 10, tzinfo=UTC),
        datetime(2026, 10, 24, 11, tzinfo=UTC),
    )
    segundo = entorno[3].crear_evento(
        usuario_id,
        "Cita",
        datetime(2026, 10, 24, 11, tzinfo=UTC),
        datetime(2026, 10, 24, 12, tzinfo=UTC),
    )

    resultado = herramienta(entorno, "agenda_cancelar_evento").ejecutar(
        usuario_id,
        {"titulo": "CITA"},
    )

    assert resultado["ok"] is False
    assert {item["id"] for item in resultado["candidatos"]} == {
        str(primero.id),
        str(segundo.id),
    }


def test_recordatorio_se_puede_cancelar_por_mensaje(entorno):
    usuario_id = entorno[1].id
    recordatorio = entorno[6].programar(
        usuario_id,
        "Llamar a Marta",
        datetime(2026, 10, 24, 10, tzinfo=UTC),
    )

    resultado = herramienta(entorno, "recordatorios_cancelar").ejecutar(
        usuario_id,
        {"mensaje": "LLAMAR A MARTA"},
    )

    assert resultado["datos"]["id"] == str(recordatorio.id)
    assert resultado["datos"]["estado"] == "cancelado"


def test_mensajes_de_recordatorio_ambiguos_devuelven_candidatos(entorno):
    usuario_id = entorno[1].id
    primero = entorno[6].programar(
        usuario_id, "Llamar", datetime(2026, 10, 24, 10, tzinfo=UTC)
    )
    segundo = entorno[6].programar(
        usuario_id, "Llamar", datetime(2026, 10, 24, 11, tzinfo=UTC)
    )

    resultado = herramienta(entorno, "recordatorios_cancelar").ejecutar(
        usuario_id,
        {"mensaje": "Llamar"},
    )

    assert resultado["ok"] is False
    assert {item["id"] for item in resultado["candidatos"]} == {
        str(primero.id),
        str(segundo.id),
    }


def test_nuevos_esquemas_de_herramientas_no_exponen_usuario_id(entorno):
    nombres = {
        "habitos_listar",
        "recordatorios_listar",
        "habitos_registrar_progreso",
        "objetivos_pausar",
        "agenda_cancelar_evento",
        "recordatorios_cancelar",
    }
    for item in entorno[0].listar():
        if item.nombre in nombres:
            assert "usuario_id" not in item.esquema_json().get("properties", {})


def test_crear_y_listar_objetivos_con_filtro(entorno):
    usuario_id = entorno[1].id
    crear = herramienta(entorno, "objetivos_crear")
    objetivo = crear.ejecutar(
        usuario_id,
        {"nombre": "Aprender", "fecha_limite": "2026-12-01"},
    )["datos"]
    pausar = herramienta(entorno, "objetivos_pausar").ejecutar(
        usuario_id, {"objetivo_id": objetivo["id"]}
    )
    assert pausar["datos"]["estado"] == "pausado"
    listar = herramienta(entorno, "objetivos_listar").ejecutar(
        usuario_id, {"estado": "pausado"}
    )
    assert [item["id"] for item in listar["datos"]] == [objetivo["id"]]


def test_herramientas_de_objetivos_progreso_reanudar_cancelar(entorno):
    usuario_id = entorno[1].id
    objetivo = herramienta(entorno, "objetivos_crear").ejecutar(
        usuario_id, {"nombre": "Meta"}
    )["datos"]
    id_objetivo = objetivo["id"]
    assert herramienta(entorno, "objetivos_actualizar_progreso").ejecutar(
        usuario_id, {"objetivo_id": id_objetivo, "progreso": 40}
    )["datos"]["progreso"] == 40
    herramienta(entorno, "objetivos_pausar").ejecutar(
        usuario_id, {"objetivo_id": id_objetivo}
    )
    assert herramienta(entorno, "objetivos_reanudar").ejecutar(
        usuario_id, {"objetivo_id": id_objetivo}
    )["datos"]["estado"] == "activo"
    assert herramienta(entorno, "objetivos_cancelar").ejecutar(
        usuario_id, {"objetivo_id": id_objetivo}
    )["datos"]["estado"] == "cancelado"


def test_programar_cancelar_y_listar_recordatorios(entorno):
    usuario_id = entorno[1].id
    programado = herramienta(entorno, "recordatorios_programar").ejecutar(
        usuario_id,
        {"mensaje": "Llamar", "cuando": "2026-10-24T10:00:00+00:00"},
    )
    assert programado["ok"] is True
    pendientes = herramienta(
        entorno, "recordatorios_pendientes_del_dia"
    ).ejecutar(usuario_id, {"dia": "2026-10-24"})
    assert [item["mensaje"] for item in pendientes["datos"]] == ["Llamar"]
    cancelado = herramienta(entorno, "recordatorios_cancelar").ejecutar(
        usuario_id, {"recordatorio_id": programado["datos"]["id"]}
    )
    assert cancelado["datos"]["estado"] == "cancelado"


def test_recordatorio_pasado_devuelve_error_de_servicio(entorno):
    resultado = herramienta(entorno, "recordatorios_programar").ejecutar(
        entorno[1].id,
        {"mensaje": "Pasado", "cuando": "2026-10-23T11:00:00+00:00"},
    )
    assert resultado == {
        "ok": False,
        "error": "La hora del recordatorio (2026-10-23 11:00) ya ha pasado.",
    }


def test_resumen_del_dia_compone_servicios_reales(entorno):
    usuario_id = entorno[1].id
    agenda = entorno[3]
    habitos = entorno[4]
    recordatorios = entorno[6]
    agenda.crear_evento(
        usuario_id,
        "Entrenar",
        datetime(2026, 10, 24, 10, tzinfo=UTC),
        datetime(2026, 10, 24, 11, tzinfo=UTC),
    )
    habitos.crear_habito(usuario_id, "Leer")
    recordatorios.programar(
        usuario_id,
        "Llamar",
        datetime(2026, 10, 24, 12, tzinfo=UTC),
    )
    resultado = herramienta(entorno, "resumen_del_dia").ejecutar(
        usuario_id, {"dia": "2026-10-24"}
    )
    assert resultado["datos"] == {
        "dia": "2026-10-24",
        "eventos": [{"titulo": "Entrenar", "inicio": "12:00", "fin": "13:00"}],
        "habitos_pendientes": ["Leer"],
        "recordatorios": ["Llamar"],
    }


def test_resumen_rechaza_usuario_inexistente_con_error_de_servicio(entorno):
    resultado = herramienta(entorno, "resumen_del_dia").ejecutar(
        uuid4(), {"dia": "2026-10-24"}
    )
    assert resultado["ok"] is False
    assert resultado["error"].startswith("No existe el usuario")
