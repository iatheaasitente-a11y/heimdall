import json
from io import BytesIO
from types import SimpleNamespace
from urllib.error import URLError
from uuid import uuid4
from unittest.mock import patch

import pytest

from app.llm import (
    ErrorRespuestaLLM,
    FrenosLLM,
    MotorFalso,
    MotorLLM,
    MotorNube,
    MotorOllama,
    RespuestaEstructurada,
    crear_motor,
)


class MotorQueFalla(MotorLLM):
    """Motor controlado para comprobar fallos absorbidos por los frenos."""

    def __init__(self, error):
        """Guarda el error que se lanzará al consultar."""
        self.error = error
        self.llamadas = 0

    def interpretar(self, historial, herramientas):
        """Incrementa las llamadas y lanza el error configurado."""
        del historial, herramientas
        self.llamadas += 1
        raise self.error


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
    assert payload["options"] == {"temperature": 0}
    assert payload["keep_alive"] == "30m"
    assert payload["messages"][-1] == {
        "role": "user",
        "content": "¿Qué tengo hoy?",
    }


def test_ollama_calentar_carga_el_modelo_con_una_peticion_minima():
    with patch(
        "app.llm.ollama.urlopen",
        return_value=BytesIO(b"{}"),
    ) as urlopen:
        MotorOllama().calentar()
    request = urlopen.call_args.args[0]
    payload = json.loads(request.data)
    assert payload["model"] == "llama3.2:3b"
    assert payload["messages"] == [{"role": "user", "content": ""}]
    assert payload["options"] == {"temperature": 0}
    assert payload["keep_alive"] == "30m"
    assert urlopen.call_args.kwargs["timeout"] == 30.0


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


def test_timeout_se_puede_configurar_por_entorno(monkeypatch):
    monkeypatch.setenv("HEIMDALL_LLM_TIMEOUT", "3.5")
    motor = MotorOllama()
    respuesta = {
        "message": {
            "content": json.dumps(
                {"intencion": "resumen_del_dia", "campos": {}, "confianza": 0.9}
            )
        }
    }
    cuerpo = json.dumps(respuesta).encode("utf-8")
    with patch("app.llm.ollama.urlopen", return_value=BytesIO(cuerpo)) as urlopen:
        motor.interpretar([], [])
    assert urlopen.call_args.kwargs["timeout"] == 3.5


def test_timeout_normal_sigue_siendo_de_diez_segundos():
    assert MotorOllama()._timeout == 10.0


def test_timeout_explicito_prevalece_sobre_el_entorno(monkeypatch):
    monkeypatch.setenv("HEIMDALL_LLM_TIMEOUT", "3.5")
    assert MotorOllama(timeout=2.5)._timeout == 2.5


def test_timeout_de_entorno_invalido_se_rechaza(monkeypatch):
    monkeypatch.setenv("HEIMDALL_LLM_TIMEOUT", "invalido")
    with pytest.raises(ValueError, match="HEIMDALL_LLM_TIMEOUT"):
        MotorOllama()


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


@pytest.mark.parametrize(
    "respuesta",
    [
        SimpleNamespace(),
        SimpleNamespace(confianza="alta"),
        SimpleNamespace(confianza=float("nan")),
    ],
)
def test_frenos_descartan_confianza_ausente_o_ilegible(monkeypatch, respuesta):
    motor = MotorFalso()
    monkeypatch.setattr(
        motor,
        "interpretar",
        lambda _historial, _herramientas: respuesta,
    )
    frenos = FrenosLLM(motor)

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
    "error",
    [OSError("sin servicio"), ErrorRespuestaLLM("respuesta inválida")],
)
def test_frenos_descartan_errores_del_motor_y_consumen_la_cuota(error):
    motor = MotorQueFalla(error)
    frenos = FrenosLLM(motor, max_consultas=1)
    conversacion_id = uuid4()
    assert frenos.consultar(conversacion_id, [], []) is None
    assert frenos.consultar(conversacion_id, [], []) is None
    assert motor.llamadas == 1


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
