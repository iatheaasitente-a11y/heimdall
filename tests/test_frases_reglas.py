import csv
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.agents import AgentePersonal
from app.tools.base import Herramienta
from app.tools.esquemas import (
    ActualizarProgresoObjetivo,
    ConsultarHabito,
    CrearEvento,
    ListarHabitos,
    ListarObjetivos,
    ProgramarRecordatorio,
    RegistrarProgresoHabito,
    ResumenDia,
)
from app.tools.registro import RegistroHerramientas

ARCHIVO_FRASES = Path(__file__).parent / "datos" / "frases.csv"
AHORA = datetime(2026, 10, 23, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))
INTENCIONES = {
    "agenda_crear_evento",
    "agenda_cancelar_evento",
    "agenda_completar_evento",
    "agenda_reprogramar_evento",
    "agenda_eventos_del_dia",
    "habitos_listar",
    "habitos_crear",
    "habitos_registrar_progreso",
    "habitos_progreso_del_dia",
    "habitos_racha",
    "objetivos_crear",
    "objetivos_actualizar_progreso",
    "objetivos_pausar",
    "objetivos_reanudar",
    "objetivos_cancelar",
    "objetivos_listar",
    "recordatorios_programar",
    "recordatorios_cancelar",
    "recordatorios_listar",
    "recordatorios_pendientes_del_dia",
    "resumen_del_dia",
    "sin_intencion",
}


def _agente():
    registro = RegistroHerramientas()

    def registrar(nombre, esquema, ejecutar):
        registro.registrar(Herramienta(nombre, nombre, esquema, ejecutar))

    def lista_de_nombres(nombres):
        return [
            {"id": str(uuid4()), "nombre": nombre}
            for nombre in nombres
        ]

    registrar(
        "resumen_del_dia",
        ResumenDia,
        lambda _usuario_id, argumentos: {
            "herramienta": "resumen_del_dia",
            "argumentos": argumentos,
        },
    )
    registrar(
        "agenda_crear_evento",
        CrearEvento,
        lambda _usuario_id, argumentos: {
            "herramienta": "agenda_crear_evento",
            "argumentos": argumentos,
        },
    )
    registrar(
        "recordatorios_programar",
        ProgramarRecordatorio,
        lambda _usuario_id, argumentos: {
            "herramienta": "recordatorios_programar",
            "argumentos": argumentos,
        },
    )
    registrar(
        "habitos_listar",
        ListarHabitos,
        lambda _usuario_id, _argumentos: lista_de_nombres(
            ("agua", "correr", "ejercicio", "inglés", "lectura", "yoga")
        ),
    )
    registrar(
        "habitos_registrar_progreso",
        RegistrarProgresoHabito,
        lambda _usuario_id, argumentos: {
            "herramienta": "habitos_registrar_progreso",
            "argumentos": argumentos,
        },
    )
    for nombre in ("habitos_progreso_del_dia", "habitos_racha"):
        registrar(
            nombre,
            ConsultarHabito,
            lambda _usuario_id, argumentos, nombre=nombre: {
                "herramienta": nombre,
                "argumentos": argumentos,
            },
        )
    registrar(
        "objetivos_listar",
        ListarObjetivos,
        lambda _usuario_id, _argumentos: lista_de_nombres(
            ("ahorrar", "correr", "curso", "Leer 10 libros", "lectura")
        ),
    )
    registrar(
        "objetivos_actualizar_progreso",
        ActualizarProgresoObjetivo,
        lambda _usuario_id, argumentos: {
            "herramienta": "objetivos_actualizar_progreso",
            "argumentos": argumentos,
        },
    )

    return AgentePersonal(
        registro,
        hoy_por_usuario=lambda _usuario_id: AHORA.date(),
        ahora_por_usuario=lambda _usuario_id: AHORA,
    )


def _filas():
    with ARCHIVO_FRASES.open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def _medir(filas):
    agente = _agente()
    atendidas = 0
    aciertos = 0
    for fila in filas:
        resultado = agente.procesar(uuid4(), uuid4(), fila["frase"])
        if resultado is not None:
            atendidas += 1
        if fila["intencion"] == "sin_intencion":
            aciertos += resultado is None
        else:
            aciertos += (
                isinstance(resultado, dict)
                and resultado.get("ok") is True
                and isinstance(resultado.get("datos"), dict)
                and resultado["datos"].get("herramienta") == fila["intencion"]
            )
    return atendidas, aciertos, len(filas)


def test_banco_tiene_cien_frases_y_separa_setenta_treinta():
    filas = _filas()

    assert len(filas) == 100
    assert len({fila["frase"] for fila in filas}) == 100
    assert {fila["conjunto"] for fila in filas} == {"ajuste", "reserva"}
    assert sum(fila["conjunto"] == "ajuste" for fila in filas) == 70
    assert sum(fila["conjunto"] == "reserva" for fila in filas) == 30
    assert {fila["intencion"] for fila in filas} <= INTENCIONES


def test_mide_por_separado_las_reglas_sobre_ajuste_y_reserva():
    filas = _filas()
    for conjunto in ("ajuste", "reserva"):
        atendidas, aciertos, total = _medir(
            [fila for fila in filas if fila["conjunto"] == conjunto]
        )
        cobertura = 100 * atendidas / total
        porcentaje_aciertos = 100 * aciertos / total
        print(
            f"{conjunto}: {atendidas}/{total} atendidas "
            f"({cobertura:.1f}%); {aciertos}/{total} resultados correctos "
            f"({porcentaje_aciertos:.1f}%)"
        )
        assert 0 <= atendidas <= total
        assert 0 <= aciertos <= total
