import json
from datetime import UTC, date, datetime
from functools import partial
from inspect import isabstract
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict

from app.agents import AgenteBase, AgentePersonal
from app.llm import MotorFalso, RespuestaEstructurada
from app.tools.base import Herramienta
from app.tools.esquemas import ReprogramarEvento
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


def _registro_reprogramar_evento(llamadas):
    registro = RegistroHerramientas()

    def reprogramar(usuario_id, argumentos):
        llamadas.append((usuario_id, argumentos))
        return {"reprogramado": True}

    registro.registrar(
        Herramienta(
            "agenda_reprogramar_evento",
            "Reprograma un evento.",
            ReprogramarEvento,
            reprogramar,
        )
    )
    return registro


def _respuesta_reprogramar(evento_id, comienza, termina):
    return RespuestaEstructurada(
        "agenda_reprogramar_evento",
        {
            "evento_id": str(evento_id),
            "comienza": comienza,
            "termina": termina,
        },
        0.9,
    )


def _historial_confirmacion(propuesta, texto):
    return [
        {
            "role": "assistant",
            "content": json.dumps(propuesta, ensure_ascii=False),
        },
        {"role": "user", "content": texto},
    ]


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
    assert agente.procesar(uuid4(), uuid4(), "Hola") == {
        "ok": True,
        "datos": "¡Hola! ¿En qué te ayudo?",
    }


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
        "role": "assistant",
        "content": "esperando: ¿Qué día quieres?",
    }
    assert [
        mensaje["content"]
        for mensaje in motor.ultimo_historial
        if mensaje["role"] == "user"
    ] == ["petición 2", "petición 3", "petición 4", "mañana"]
    assert llamadas == [(usuario_id, {"dia": date(2026, 11, 12)})]


def test_cortesia_si_confianza_baja_o_cuota_agotada():
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
    cortesia = {
        "ok": True,
        "datos": {
            "mensaje": "Hola. Puedo ayudarte con agenda, hábitos, objetivos y recordatorios."
        },
    }
    assert agente.procesar(usuario_id, conversacion_id, "resumen") == cortesia
    assert agente.procesar(usuario_id, conversacion_id, "resumen") == cortesia
    assert agente.procesar(usuario_id, conversacion_id, "resumen") == cortesia
    assert agente.procesar(usuario_id, conversacion_id, "resumen") == cortesia
    assert llamadas == []


def test_hola_sin_intencion_devuelve_saludo_de_cortesia():
    agente = AgentePersonal(
        _registro_resumen([]),
        MotorFalso([RespuestaEstructurada("resumen_del_dia", {}, 0.2)]),
    )

    resultado = agente.procesar(uuid4(), uuid4(), "hola")

    assert resultado == {
        "ok": True,
        "datos": "¡Hola! ¿En qué te ayudo?",
    }


def test_sin_intencion_repite_confirmacion_pendiente_en_vez_de_saludar():
    llamadas = []
    usuario_id = uuid4()
    conversacion_id = uuid4()
    evento_id = uuid4()
    motor = MotorFalso(
        [
            _respuesta_reprogramar(
                evento_id,
                "2026-11-15T12:00:00+00:00",
                "2026-11-15T13:00:00+00:00",
            ),
            RespuestaEstructurada("intencion", {}, 0.2),
        ]
    )
    agente = AgentePersonal(_registro_reprogramar_evento(llamadas), motor)
    propuesta = agente.procesar(usuario_id, conversacion_id, "reprograma")

    resultado = agente.procesar(
        usuario_id,
        conversacion_id,
        "xyz",
        _historial_confirmacion(propuesta, "xyz"),
    )

    assert resultado["confirmacion_pendiente"] == propuesta["confirmacion_pendiente"]
    assert resultado["error"] == propuesta["error"]
    assert "mensaje" not in resultado.get("datos", {})
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


def test_llm_pide_confirmacion_con_operacion_elemento_y_cambios():
    llamadas = []
    usuario_id = uuid4()
    conversacion_id = uuid4()
    evento_id = uuid4()
    motor = MotorFalso(
        [
            _respuesta_reprogramar(
                evento_id,
                "2026-11-15T12:00:00+00:00",
                "2026-11-15T13:00:00+00:00",
            )
        ]
    )
    agente = AgentePersonal(_registro_reprogramar_evento(llamadas), motor)

    resultado = agente.procesar(
        usuario_id,
        conversacion_id,
        "reprograma",
    )

    assert resultado["ok"] is False
    assert f"reprogramar el evento «{evento_id}»" in resultado["error"]
    assert "nuevo inicio 2026-11-15T12:00:00Z" in resultado["error"]
    assert "nuevo fin 2026-11-15T13:00:00Z" in resultado["error"]
    assert resultado["confirmacion_pendiente"] == {
        "usuario_id": str(usuario_id),
        "conversacion_id": str(conversacion_id),
        "herramienta": "agenda_reprogramar_evento",
        "campos": {
            "evento_id": str(evento_id),
            "titulo": None,
            "comienza": "2026-11-15T12:00:00Z",
            "termina": "2026-11-15T13:00:00Z",
        },
        "requiere_reconfirmacion": False,
    }
    assert llamadas == []


@pytest.mark.parametrize(
    "nombre",
    [
        "agenda_cancelar_evento",
        "agenda_completar_evento",
        "objetivos_pausar",
        "objetivos_reanudar",
        "objetivos_cancelar",
        "recordatorios_cancelar",
    ],
)
def test_toda_operacion_de_cancelacion_o_estado_llm_pide_confirmacion(nombre):
    llamadas = []
    registro = RegistroHerramientas()
    registro.registrar(
        Herramienta(
            nombre,
            "Operación que requiere confirmación.",
            ArgumentosResumen,
            lambda usuario_id, argumentos: llamadas.append((usuario_id, argumentos)),
        )
    )
    motor = MotorFalso(
        [RespuestaEstructurada(nombre, {"dia": "2026-11-12"}, 0.9)]
    )
    agente = AgentePersonal(registro, motor)

    resultado = agente.procesar(uuid4(), uuid4(), "ejecuta la operación")

    assert resultado["ok"] is False
    assert resultado["confirmacion_pendiente"]["herramienta"] == nombre
    assert "¿Confirmas?" in resultado["error"]
    assert llamadas == []


def test_confirmacion_afirmativa_ejecuta_una_vez_con_argumentos_revalidados():
    llamadas = []
    usuario_id = uuid4()
    conversacion_id = uuid4()
    evento_id = uuid4()
    motor = MotorFalso(
        [
            _respuesta_reprogramar(
                evento_id,
                "2026-11-15T12:00:00+00:00",
                "2026-11-15T13:00:00+00:00",
            ),
            RespuestaEstructurada("herramienta_inexistente", {}, 0.9),
        ]
    )
    agente = AgentePersonal(_registro_reprogramar_evento(llamadas), motor)
    propuesta = agente.procesar(
        usuario_id,
        conversacion_id,
        "reprograma",
    )

    ejecutado = agente.procesar(
        usuario_id,
        conversacion_id,
        "Sí, confirmo.",
        _historial_confirmacion(propuesta, "Sí, confirmo."),
    )
    repetido = agente.procesar(
        usuario_id,
        conversacion_id,
        "sí",
        [
            *_historial_confirmacion(propuesta, "Sí, confirmo."),
            {"role": "assistant", "content": json.dumps(ejecutado)},
            {"role": "user", "content": "sí"},
        ],
    )

    assert ejecutado == {"ok": True, "datos": {"reprogramado": True}}
    assert llamadas == [
        (
            usuario_id,
            {
                "evento_id": evento_id,
                "titulo": None,
                "comienza": datetime(2026, 11, 15, 12, tzinfo=UTC),
                "termina": datetime(2026, 11, 15, 13, tzinfo=UTC),
            },
        )
    ]
    assert repetido is None


def test_rechazar_propuesta_no_ejecuta_ni_cancela_evento():
    llamadas = []
    usuario_id = uuid4()
    conversacion_id = uuid4()
    evento_id = uuid4()
    agente = AgentePersonal(
        _registro_reprogramar_evento(llamadas),
        MotorFalso(
            [
                _respuesta_reprogramar(
                    evento_id,
                    "2026-11-15T12:00:00+00:00",
                    "2026-11-15T13:00:00+00:00",
                )
            ]
        ),
    )
    propuesta = agente.procesar(usuario_id, conversacion_id, "reprograma")

    resultado = agente.procesar(
        usuario_id,
        conversacion_id,
        "no",
        _historial_confirmacion(propuesta, "no"),
    )

    assert resultado == {"ok": False, "error": "Propuesta rechazada; no se ejecutó."}
    assert llamadas == []


def test_respuesta_ambigua_repite_la_propuesta_sin_cambiarla():
    llamadas = []
    usuario_id = uuid4()
    conversacion_id = uuid4()
    evento_id = uuid4()
    motor = MotorFalso(
        [
            _respuesta_reprogramar(
                evento_id,
                "2026-11-15T12:00:00+00:00",
                "2026-11-15T13:00:00+00:00",
            ),
            RespuestaEstructurada("herramienta_inexistente", {}, 0.9),
        ]
    )
    agente = AgentePersonal(_registro_reprogramar_evento(llamadas), motor)
    propuesta = agente.procesar(usuario_id, conversacion_id, "reprograma")

    repetida = agente.procesar(
        usuario_id,
        conversacion_id,
        "tal vez",
        _historial_confirmacion(propuesta, "tal vez"),
    )

    assert repetida["confirmacion_pendiente"] == propuesta["confirmacion_pendiente"]
    assert repetida["error"] == propuesta["error"]
    assert llamadas == []


def test_llm_no_ejecuta_otra_herramienta_ante_una_confirmacion_pendiente():
    llamadas = []
    resumen_llamadas = []
    usuario_id = uuid4()
    conversacion_id = uuid4()
    evento_id = uuid4()
    registro = _registro_reprogramar_evento(llamadas)
    for herramienta in _registro_resumen(resumen_llamadas).listar():
        registro.registrar(herramienta)
    motor = MotorFalso(
        [
            _respuesta_reprogramar(
                evento_id,
                "2026-11-15T12:00:00+00:00",
                "2026-11-15T13:00:00+00:00",
            ),
            RespuestaEstructurada(
                "resumen_del_dia",
                {"dia": "2026-11-12"},
                0.9,
            ),
        ]
    )
    agente = AgentePersonal(
        registro,
        motor,
        hoy_por_usuario=partial(_fecha_fija, fecha=date(2026, 11, 12)),
    )
    propuesta = agente.procesar(usuario_id, conversacion_id, "reprograma")

    resultado = agente.procesar(
        usuario_id,
        conversacion_id,
        "tal vez",
        _historial_confirmacion(propuesta, "tal vez"),
    )

    assert resultado["confirmacion_pendiente"] == propuesta["confirmacion_pendiente"]
    assert resumen_llamadas == []
    assert llamadas == []


@pytest.mark.parametrize("cambiar", ["usuario", "conversacion"])
def test_propuesta_no_se_puede_confirmar_desde_otro_ambito(cambiar):
    llamadas = []
    usuario_id = uuid4()
    conversacion_id = uuid4()
    evento_id = uuid4()
    motor = MotorFalso(
        [
            _respuesta_reprogramar(
                evento_id,
                "2026-11-15T12:00:00+00:00",
                "2026-11-15T13:00:00+00:00",
            ),
            RespuestaEstructurada("herramienta_inexistente", {}, 0.9),
        ]
    )
    agente = AgentePersonal(_registro_reprogramar_evento(llamadas), motor)
    propuesta = agente.procesar(usuario_id, conversacion_id, "reprograma")
    otro_usuario = uuid4() if cambiar == "usuario" else usuario_id
    otra_conversacion = (
        uuid4() if cambiar == "conversacion" else conversacion_id
    )

    resultado = agente.procesar(
        otro_usuario,
        otra_conversacion,
        "sí",
        _historial_confirmacion(propuesta, "sí"),
    )

    assert resultado is None
    assert llamadas == []


def test_modificar_propuesta_reemplaza_argumentos_y_solicita_confirmacion_nueva():
    llamadas = []
    usuario_id = uuid4()
    conversacion_id = uuid4()
    evento_id = uuid4()
    motor = MotorFalso(
        [
            _respuesta_reprogramar(
                evento_id,
                "2026-11-15T12:00:00+00:00",
                "2026-11-15T13:00:00+00:00",
            ),
            _respuesta_reprogramar(
                evento_id,
                "2026-11-15T14:00:00+00:00",
                "2026-11-15T15:00:00+00:00",
            ),
        ]
    )
    agente = AgentePersonal(_registro_reprogramar_evento(llamadas), motor)
    propuesta = agente.procesar(usuario_id, conversacion_id, "reprograma")

    modificada = agente.procesar(
        usuario_id,
        conversacion_id,
        "mejor a las dos",
        _historial_confirmacion(propuesta, "mejor a las dos"),
    )

    assert "nuevo inicio 2026-11-15T14:00:00Z" in modificada["error"]
    assert "nuevo fin 2026-11-15T15:00:00Z" in modificada["error"]
    assert modificada["confirmacion_pendiente"]["campos"]["comienza"] == (
        "2026-11-15T14:00:00Z"
    )
    assert llamadas == []


def test_cambio_de_tema_determinista_conserva_propuesta_y_pide_reconfirmar():
    llamadas = []
    usuario_id = uuid4()
    conversacion_id = uuid4()
    evento_id = uuid4()
    registro = _registro_reprogramar_evento(llamadas)
    resumen_llamadas = []
    for herramienta in _registro_resumen(resumen_llamadas).listar():
        registro.registrar(herramienta)
    agente = AgentePersonal(
        registro,
        MotorFalso(
            [
                _respuesta_reprogramar(
                    evento_id,
                    "2026-11-15T12:00:00+00:00",
                    "2026-11-15T13:00:00+00:00",
                )
            ]
        ),
        hoy_por_usuario=partial(_fecha_fija, fecha=date(2026, 11, 12)),
    )
    propuesta = agente.procesar(usuario_id, conversacion_id, "reprograma")

    tema = agente.procesar(
        usuario_id,
        conversacion_id,
        "¿Qué tengo hoy?",
        _historial_confirmacion(propuesta, "¿Qué tengo hoy?"),
    )
    reexpuesta = agente.procesar(
        usuario_id,
        conversacion_id,
        "sí",
        _historial_confirmacion(tema, "sí"),
    )
    ejecutado = agente.procesar(
        usuario_id,
        conversacion_id,
        "sí",
        _historial_confirmacion(reexpuesta, "sí"),
    )

    assert tema["datos"]["dia"] == "2026-11-12"
    assert tema["confirmacion_pendiente"]["requiere_reconfirmacion"] is True
    assert reexpuesta["confirmacion_pendiente"]["requiere_reconfirmacion"] is False
    assert "reprogramar el evento" in reexpuesta["error"]
    assert llamadas[0][0] == usuario_id
    assert len(llamadas) == 1
