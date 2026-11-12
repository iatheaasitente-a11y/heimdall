import json
from io import BytesIO
from urllib.error import URLError
from uuid import uuid4
from unittest.mock import patch

import pytest

from app.llm import (
    ErrorRespuestaLLM,
    FrenosLLM,
    MotorFalso,
    MotorNube,
    MotorOllama,
    RespuestaEstructurada,
    crear_motor,
)


def test_respuesta_estructurada_contiene_intencion_argumentos_y_confianza():
    respuesta = RespuestaEstructurada("agenda_crear_evento", {"titulo": "Cita"}, 0.9)
    assert respuesta.intencion == "agenda_crear_evento"
    assert respuesta.campos == {"titulo": "Cita"}
    assert respuesta.confianza == 0.9


@pytest.mark.parametrize("confianza", [-0.1, 1.1])
def test_respuesta_rechaza_confianza_fuera_de_rango(confianza):
    with pytest.raises(ValueError):
        RespuestaEstructurada("agenda", {}, confianza)


def test_respuesta_rechaza_intencion_vacia():
    with pytest.raises(ValueError):
        RespuestaEstructurada("  ")


def test_motor_falso_devuelve_respuesta_y_guarda_solicitud():
    respuesta = RespuestaEstructurada("agenda_eventos_del_dia", {"dia": "2026-11-12"}, 0.8)
    motor = MotorFalso([respuesta])
    historial = [{"role": "user", "content": "¿Qué tengo hoy?"}]
    herramientas = [{"name": "agenda_eventos_del_dia"}]
    assert motor.interpretar(historial, herramientas) == respuesta
    assert motor.ultimo_historial == historial
    assert motor.ultimas_herramientas == herramientas


def test_motor_falso_sin_respuestas_falla_explicito():
    with pytest.raises(RuntimeError, match="no tiene más respuestas"):
        MotorFalso().interpretar([], [])


def test_motor_ollama_envia_salida_estructurada_sin_red_real():
    contenido = {
        "message": {
            "content": json.dumps(
                {
                    "intencion": "agenda_eventos_del_dia",
                    "campos": {"dia": "2026-11-12"},
                    "confianza": 0.82,
                }
            )
        }
    }
    motor = MotorOllama(timeout=2.5)
    with patch(
        "app.llm.ollama.urlopen",
        return_value=BytesIO(json.dumps(contenido).encode("utf-8")),
    ) as urlopen:
        respuesta = motor.interpretar(
            [{"role": "user", "content": "¿Qué tengo hoy?"}],
            [{"name": "agenda_eventos_del_dia", "schema": {"type": "object"}}],
        )
    assert respuesta == RespuestaEstructurada(
        "agenda_eventos_del_dia", {"dia": "2026-11-12"}, 0.82
    )
    urlopen.assert_called_once()
    request = urlopen.call_args.args[0]
    payload = json.loads(request.data)
    assert request.full_url == "http://127.0.0.1:11434/api/chat"
    assert urlopen.call_args.kwargs["timeout"] == 2.5
    assert payload["model"] == "llama3.2:3b"
    assert payload["stream"] is False
    assert payload["format"]["additionalProperties"] is False
    assert payload["messages"][-1] == {
        "role": "user",
        "content": "¿Qué tengo hoy?",
    }


def test_ollama_no_reintenta_si_expira_el_tiempo():
    motor = MotorOllama()
    with patch("app.llm.ollama.urlopen", side_effect=TimeoutError("timeout")) as urlopen:
        with pytest.raises(TimeoutError):
            motor.interpretar([], [])
    urlopen.assert_called_once()


def test_ollama_devuelve_error_claro_si_la_respuesta_no_es_valida():
    with patch(
        "app.llm.ollama.urlopen",
        return_value=BytesIO(b'{"message":{"content":"{}"}}'),
    ):
        with pytest.raises(ErrorRespuestaLLM):
            MotorOllama().interpretar([], [])


@pytest.mark.parametrize(
    "respuesta",
    [
        {"intencion": "", "campos": {}, "confianza": 0.9},
        {"intencion": "agenda", "campos": {}, "confianza": 1.1},
    ],
)
def test_ollama_convierte_campos_invalidos_en_error_de_respuesta(respuesta):
    cuerpo = {"message": {"content": json.dumps(respuesta)}}
    with patch(
        "app.llm.ollama.urlopen",
        return_value=BytesIO(json.dumps(cuerpo).encode("utf-8")),
    ):
        with pytest.raises(ErrorRespuestaLLM):
            MotorOllama().interpretar([], [])


def test_ollama_propaga_error_de_conexion_sin_reintentar():
    with patch("app.llm.ollama.urlopen", side_effect=URLError("sin servidor")) as urlopen:
        with pytest.raises(URLError):
            MotorOllama().interpretar([], [])
    urlopen.assert_called_once()


def test_timeout_invalido_se_rechaza():
    with pytest.raises(ValueError):
        MotorOllama(timeout=0)


def test_motor_esta_apagado_por_defecto(monkeypatch):
    monkeypatch.delenv("HEIMDALL_LLM", raising=False)
    assert crear_motor() is None


def test_configuracion_selecciona_ollama_o_nube(monkeypatch):
    monkeypatch.setenv("HEIMDALL_LLM", "ollama")
    assert isinstance(crear_motor(), MotorOllama)
    monkeypatch.setenv("HEIMDALL_LLM", "nube")
    assert isinstance(crear_motor(), MotorNube)


def test_configuracion_rechaza_valores_desconocidos(monkeypatch):
    monkeypatch.setenv("HEIMDALL_LLM", "api")
    with pytest.raises(ValueError, match="apagado, ollama, nube"):
        crear_motor()


def test_motor_nube_es_un_esqueleto_sin_red_ni_clave():
    with pytest.raises(NotImplementedError):
        MotorNube().interpretar([], [])


def test_frenos_descartan_respuestas_de_baja_confianza():
    motor = MotorFalso([RespuestaEstructurada("intencion", {}, 0.4)])
    frenos = FrenosLLM(motor, confianza_minima=0.65)
    assert frenos.consultar(uuid4(), [], []) is None


def test_frenos_aceptan_el_umbral_exactamente():
    respuesta = RespuestaEstructurada("intencion", {}, 0.65)
    frenos = FrenosLLM(MotorFalso([respuesta]), confianza_minima=0.65)
    assert frenos.consultar(uuid4(), [], []) == respuesta


def test_frenos_aplican_limite_por_conversacion():
    respuesta = RespuestaEstructurada("intencion", {}, 0.9)
    motor = MotorFalso([respuesta, respuesta, respuesta])
    frenos = FrenosLLM(motor, max_consultas=2)
    conversacion = uuid4()
    assert frenos.consultar(conversacion, [], []) == respuesta
    assert frenos.consultar(conversacion, [], []) == respuesta
    assert frenos.consultar(conversacion, [], []) is None


def test_frenos_mantienen_cuotas_separadas_por_conversacion():
    respuesta = RespuestaEstructurada("intencion", {}, 0.9)
    motor = MotorFalso([respuesta, respuesta])
    frenos = FrenosLLM(motor, max_consultas=1)
    assert frenos.consultar(uuid4(), [], []) == respuesta
    assert frenos.consultar(uuid4(), [], []) == respuesta


@pytest.mark.parametrize(
    "max_consultas,confianza",
    [(0, 0.5), (1, -0.1), (1, 1.1)],
)
def test_frenos_validan_configuracion(max_consultas, confianza):
    with pytest.raises(ValueError):
        FrenosLLM(
            MotorFalso([RespuestaEstructurada("intencion", {}, 1)]),
            max_consultas=max_consultas,
            confianza_minima=confianza,
        )
