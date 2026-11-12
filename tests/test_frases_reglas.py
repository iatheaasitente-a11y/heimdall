import csv
from datetime import date
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from app.agents import AgentePersonal
from app.tools.base import Herramienta
from app.tools.registro import RegistroHerramientas

ARCHIVO_FRASES = Path(__file__).parent / "datos" / "frases.csv"


class ParametrosResumen(BaseModel):
    dia: date


def _agente():
    registro = RegistroHerramientas()
    registro.registrar(
        Herramienta(
            "resumen_del_dia",
            "Resume el día.",
            ParametrosResumen,
            lambda _usuario_id, argumentos: {"dia": argumentos["dia"]},
        )
    )
    return AgentePersonal(
        registro,
        hoy_por_usuario=lambda _usuario_id: date(2026, 11, 12),
    )


def test_banco_inicial_tiene_treinta_frases_y_etiquetas():
    with ARCHIVO_FRASES.open(encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    assert len(filas) == 30
    assert {fila["intencion"] for fila in filas} == {
        "agenda_eventos_del_dia",
        "agenda_crear_evento",
        "agenda_cancelar_evento",
        "habitos_progreso_del_dia",
        "habitos_registrar_progreso",
        "habitos_crear",
        "habitos_racha",
        "objetivos_listar",
        "objetivos_pausar",
        "objetivos_reanudar",
        "objetivos_crear",
        "objetivos_cancelar",
        "objetivos_progreso",
        "recordatorios_pendientes_del_dia",
        "recordatorios_programar",
        "recordatorios_cancelar",
        "resumen_del_dia",
    }


def test_banco_mide_cuantas_frases_resuelve_el_agente_solo_con_reglas():
    with ARCHIVO_FRASES.open(encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    agente = _agente()
    resueltas = sum(
        agente.procesar(uuid4(), uuid4(), fila["frase"]) is not None
        for fila in filas
    )
    assert 0 < resueltas <= len(filas)
