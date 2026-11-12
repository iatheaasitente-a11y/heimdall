import json
from datetime import date
from functools import partial
from inspect import isabstract
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict

from app.agents import AgenteBase, AgentePersonal
from app.llm import MotorFalso, RespuestaEstructurada
from app.tools.base import Herramienta
from app.tools.registro import RegistroHerramientas


class ArgumentosResumen(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dia: date


def _fecha_fija(usuario_id, *, fecha):
    del usuario_id
    return fecha


def _registro_resumen(llamadas):
    registro = RegistroHerramientas()

    def resumir(usuario_id, argumentos):
        llamadas.append((usuario_id, argumentos))
        return {"dia": argumentos["dia"].isoformat(), "eventos": []}

    registro.registrar(
        Herramienta(
            "resumen_del_dia",
            "Resume el día del usuario.",
            ArgumentosResumen,
            resumir,
        )
    )
    return registro


def test_agente_base_es_abstracto():
    assert isabstract(AgenteBase)


def test_regla_resumen_del_dia_usa_herramienta_y_fecha_inyectada():
    llamadas = []
    usuario_id = uuid4()
    motor = MotorFalso()
    agente = AgentePersonal(
        _registro_resumen(llamadas),
        motor,
        hoy_por_usuario=partial(_fecha_fija, fecha=date(2026, 11, 12)),
    )
    resultado = agente.procesar(
        usuario_id,
        uuid4(),
        "¿Qué tengo hoy?",
        [{"role": "user", "content": "¿Qué tengo hoy?"}],
    )
    assert resultado == {
        "ok": True,
        "datos": {"dia": "2026-11-12", "eventos": []},
    }
    assert llamadas == [(usuario_id, {"dia": date(2026, 11, 12)})]
    assert motor.ultimo_historial == []


def test_regla_reconoce_variantes_sin_acentos_o_puntuacion():
    llamadas = []
    agente = AgentePersonal(
        _registro_resumen(llamadas),
        hoy_por_usuario=partial(_fecha_fija, fecha=date(2026, 1, 2)),
    )
    for frase in ("que tengo para hoy", "¿Qué hay hoy?"):
        resultado = agente.procesar(uuid4(), uuid4(), frase)
        assert resultado is not None
        assert resultado["ok"] is True
    assert len(llamadas) == 2


def test_regla_tiene_prioridad_sobre_motor_llm():
    llamadas = []
    motor = MotorFalso([RespuestaEstructurada("resumen_del_dia", {}, 0.9)])
    agente = AgentePersonal(
        _registro_resumen(llamadas),
        motor,
        hoy_por_usuario=partial(_fecha_fija, fecha=date(2026, 1, 2)),
    )
    agente.procesar(uuid4(), uuid4(), "¿Qué tengo hoy?")
    assert motor.ultimo_historial == []


def test_mensaje_no_reconocido_sin_motor_devuelve_none():
    agente = AgentePersonal(_registro_resumen([]))
    assert agente.procesar(uuid4(), uuid4(), "Hola") is None


def test_mensaje_no_reconocido_usa_motor_y_ejecuta_herramienta():
    llamadas = []
    usuario_id = uuid4()
    conversacion_id = uuid4()
    respuesta = RespuestaEstructurada(
        "resumen_del_dia",
        {"dia": "2026-11-12"},
        0.9,
    )
    motor = MotorFalso([respuesta])
    registro = _registro_resumen(llamadas)
    agente = AgentePersonal(registro, motor)
    historial = [{"role": "user", "content": "Enséñame mi resumen"}]
    resultado = agente.procesar(
        usuario_id,
        conversacion_id,
        "Dame un resumen",
        historial,
    )
    assert resultado is not None
    assert resultado["ok"] is True
    assert llamadas == [(usuario_id, {"dia": date(2026, 11, 12)})]
    assert motor.ultimo_historial == historial
    assert motor.ultimas_herramientas == [
        {
            "name": "resumen_del_dia",
            "description": "Resume el día del usuario.",
            "parameters": ArgumentosResumen.model_json_schema(),
        }
    ]


def test_motor_llm_no_puede_elegir_usuario_id():
    llamadas = []
    motor = MotorFalso(
        [
            RespuestaEstructurada(
                "resumen_del_dia",
                {"dia": "2026-11-12", "usuario_id": str(uuid4())},
                0.9,
            )
        ]
    )
    agente = AgentePersonal(_registro_resumen(llamadas), motor)
    resultado = agente.procesar(uuid4(), uuid4(), "Dame un resumen")
    assert resultado is None
    assert llamadas == []


def test_motor_no_puede_inyectar_campos_que_el_esquema_no_declara():
    class ParametrosPermisivos(BaseModel):
        texto: str

    llamadas = []
    registro = RegistroHerramientas()
    registro.registrar(
        Herramienta(
            "eco",
            "Devuelve el texto.",
            ParametrosPermisivos,
            lambda _usuario_id, argumentos: llamadas.append(argumentos),
        )
    )
    motor = MotorFalso(
        [
            RespuestaEstructurada(
                "eco",
                {"texto": "válido", "campo_fuera_del_catalogo": "rechazado"},
                0.9,
            )
        ]
    )
    agente = AgentePersonal(registro, motor)

    assert agente.procesar(uuid4(), uuid4(), "repite") is None
    assert llamadas == []


def test_motor_no_puede_enviar_un_valor_invalido_al_servicio():
    llamadas = []
    motor = MotorFalso(
        [
            RespuestaEstructurada(
                "resumen_del_dia",
                {"dia": "no es una fecha"},
                0.9,
            )
        ]
    )
    agente = AgentePersonal(_registro_resumen(llamadas), motor)

    assert agente.procesar(uuid4(), uuid4(), "dame el resumen") is None
    assert llamadas == []


def test_agente_pasa_la_pregunta_pendiente_y_los_ultimos_cuatro_turnos():
    llamadas = []
    usuario_id = uuid4()
    motor = MotorFalso(
        [RespuestaEstructurada("resumen_del_dia", {"dia": "2026-11-12"}, 0.9)]
    )
    agente = AgentePersonal(_registro_resumen(llamadas), motor)
    historial = []
    for indice in range(5):
        historial.extend(
            [
                {"role": "user", "content": f"petición {indice}"},
                {"role": "assistant", "content": "respuesta anterior"},
            ]
        )
    historial.extend(
        [
            {
                "role": "assistant",
                "content": json.dumps(
                    {"ok": False, "error": "¿Qué día quieres?"},
                    ensure_ascii=False,
                ),
            },
            {"role": "user", "content": "mañana"},
        ]
    )

    resultado = agente.procesar(
        usuario_id,
        uuid4(),
        "mañana",
        historial,
    )

    assert resultado["ok"] is True
    assert motor.ultimo_historial[0] == {
        "role": "system",
        "content": "esperando: ¿Qué día quieres?",
    }
    assert [
        mensaje["content"]
        for mensaje in motor.ultimo_historial
        if mensaje["role"] == "user"
    ] == ["petición 2", "petición 3", "petición 4", "mañana"]
    assert llamadas == [(usuario_id, {"dia": date(2026, 11, 12)})]


def test_confianza_baja_o_cuota_agotada_no_ejecuta_herramienta():
    llamadas = []
    respuesta = RespuestaEstructurada(
        "resumen_del_dia",
        {"dia": "2026-01-02"},
        0.2,
    )
    motor = MotorFalso([respuesta, respuesta, respuesta])
    agente = AgentePersonal(_registro_resumen(llamadas), motor)
    usuario_id = uuid4()
    conversacion_id = uuid4()
    assert agente.procesar(usuario_id, conversacion_id, "resumen") is None
    assert agente.procesar(usuario_id, conversacion_id, "resumen") is None
    assert agente.procesar(usuario_id, conversacion_id, "resumen") is None
    assert agente.procesar(usuario_id, conversacion_id, "resumen") is None
    assert llamadas == []


def test_intencion_de_herramienta_desconocida_no_se_ejecuta():
    motor = MotorFalso([RespuestaEstructurada("herramienta_inexistente", {}, 0.9)])
    agente = AgentePersonal(_registro_resumen([]), motor)
    assert agente.procesar(uuid4(), uuid4(), "otra solicitud") is None


def test_esquema_de_herramienta_no_incluye_usuario_id():
    llamadas = []
    motor = MotorFalso(
        [
            RespuestaEstructurada(
                "resumen_del_dia",
                {"dia": "2026-11-12"},
                0.9,
            )
        ]
    )
    agente = AgentePersonal(_registro_resumen(llamadas), motor)
    agente.procesar(uuid4(), uuid4(), "otra solicitud")
    assert "usuario_id" not in str(motor.ultimas_herramientas)
