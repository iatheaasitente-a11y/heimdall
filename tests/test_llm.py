import json
import logging
from io import BytesIO
from types import SimpleNamespace
from urllib.error import URLError
from uuid import uuid4
from unittest.mock import patch

import pytest

from app.llm import (
    Catalogo,
    ErrorRespuestaLLM,
    FrenosLLM,
    MotorFalso,
    MotorLLM,
    MotorNube,
    MotorOllama,
    RespuestaEstructurada,
    RolModelo,
    crear_catalogo,
    crear_motor,
    crear_planificador,
)


MODELO_PRUEBA = "modelo-prueba"


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
    motor = MotorOllama(modelo=MODELO_PRUEBA, timeout=2.5)
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
    assert payload["model"] == MODELO_PRUEBA
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
        MotorOllama(modelo=MODELO_PRUEBA).calentar()
    request = urlopen.call_args.args[0]
    payload = json.loads(request.data)
    assert payload["model"] == MODELO_PRUEBA
    assert payload["messages"] == [{"role": "user", "content": ""}]
    assert payload["options"] == {"temperature": 0}
    assert payload["keep_alive"] == "30m"
    assert urlopen.call_args.kwargs["timeout"] == 30.0


def test_ollama_calentar_acepta_el_timeout_de_carga_aprobado():
    with patch(
        "app.llm.ollama.urlopen",
        return_value=BytesIO(b"{}"),
    ) as urlopen:
        MotorOllama(modelo=MODELO_PRUEBA).calentar(timeout=60)

    assert urlopen.call_args.kwargs["timeout"] == 60


def test_ollama_descarga_modelo_con_keep_alive_cero():
    motor = MotorOllama(modelo=MODELO_PRUEBA)
    with patch(
        "app.llm.ollama.urlopen",
        return_value=BytesIO(b"{}"),
    ) as urlopen:
        motor.descargar(timeout=10)

    request = urlopen.call_args.args[0]
    assert request.full_url == "http://127.0.0.1:11434/api/generate"
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {
        "model": MODELO_PRUEBA,
        "keep_alive": 0,
        "stream": False,
    }
    assert urlopen.call_args.kwargs["timeout"] == 10


def test_ollama_informa_modelos_cargados():
    cuerpo = json.dumps({"models": [{"name": MODELO_PRUEBA}]}).encode("utf-8")
    motor = MotorOllama(modelo=MODELO_PRUEBA)
    with patch("app.llm.ollama.urlopen", return_value=BytesIO(cuerpo)) as urlopen:
        assert motor.modelos_cargados(timeout=10) == (MODELO_PRUEBA,)

    request = urlopen.call_args.args[0]
    assert request.full_url == "http://127.0.0.1:11434/api/ps"
    assert request.get_method() == "GET"


@pytest.mark.parametrize("cuerpo", [b"{}", b'{"models":{}}', b"not-json"])
def test_ollama_rechaza_lista_de_modelos_cargados_invalida(cuerpo):
    with patch("app.llm.ollama.urlopen", return_value=BytesIO(cuerpo)):
        with pytest.raises(ErrorRespuestaLLM, match="lista de modelos"):
            MotorOllama(modelo=MODELO_PRUEBA).modelos_cargados(timeout=10)


def test_ollama_exige_nombre_de_modelo_explicito():
    with pytest.raises(ValueError, match="explícitamente"):
        MotorOllama()


def test_ollama_no_reintenta_si_expira_el_tiempo():
    motor = MotorOllama(modelo=MODELO_PRUEBA)
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
            MotorOllama(modelo=MODELO_PRUEBA).interpretar([], [])


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
            MotorOllama(modelo=MODELO_PRUEBA).interpretar([], [])


def test_ollama_propaga_error_de_conexion_sin_reintentar():
    with patch("app.llm.ollama.urlopen", side_effect=URLError("sin servidor")) as urlopen:
        with pytest.raises(URLError):
            MotorOllama(modelo=MODELO_PRUEBA).interpretar([], [])
    urlopen.assert_called_once()


def test_timeout_invalido_se_rechaza():
    with pytest.raises(ValueError):
        MotorOllama(modelo=MODELO_PRUEBA, timeout=0)


def test_timeout_se_puede_configurar_por_entorno(monkeypatch):
    monkeypatch.setenv("HEIMDALL_LLM_TIMEOUT", "3.5")
    motor = MotorOllama(modelo=MODELO_PRUEBA)
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
    assert MotorOllama(modelo=MODELO_PRUEBA)._timeout == 10.0


def test_timeout_explicito_prevalece_sobre_el_entorno(monkeypatch):
    monkeypatch.setenv("HEIMDALL_LLM_TIMEOUT", "3.5")
    assert MotorOllama(modelo=MODELO_PRUEBA, timeout=2.5)._timeout == 2.5


def test_timeout_de_entorno_invalido_se_rechaza(monkeypatch):
    monkeypatch.setenv("HEIMDALL_LLM_TIMEOUT", "invalido")
    with pytest.raises(ValueError, match="HEIMDALL_LLM_TIMEOUT"):
        MotorOllama(modelo=MODELO_PRUEBA)


def test_motor_esta_apagado_por_defecto(monkeypatch):
    monkeypatch.delenv("HEIMDALL_LLM", raising=False)
    assert crear_motor() is None


def test_configuracion_selecciona_ollama_o_nube(monkeypatch):
    monkeypatch.setenv("HEIMDALL_MODELO_TEXTO", "modelo-texto")
    monkeypatch.setenv("HEIMDALL_LLM", "ollama")
    motor = crear_motor()
    assert isinstance(motor, MotorOllama)
    assert motor._modelo == "modelo-texto:latest"
    monkeypatch.setenv("HEIMDALL_LLM", "nube")
    assert isinstance(crear_motor(), MotorNube)


def test_configuracion_rechaza_ollama_sin_modelo_de_texto(monkeypatch):
    monkeypatch.setenv("HEIMDALL_LLM", "ollama")
    monkeypatch.delenv("HEIMDALL_MODELO_TEXTO", raising=False)

    with pytest.raises(ValueError, match="HEIMDALL_MODELO_TEXTO"):
        crear_motor()


@pytest.mark.parametrize(
    "url",
    [
        "ftp://127.0.0.1:11434/api/chat",
        "http://ollama.example.com:11434/api/chat",
        "http://localhost@ollama.example.com:11434/api/chat",
    ],
)
def test_ollama_rechaza_esquemas_y_hosts_no_locales(url):
    with pytest.raises(ValueError, match="host local"):
        MotorOllama(url=url, modelo=MODELO_PRUEBA)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434/api/chat",
        "https://127.0.0.1:11434/api/chat",
        "http://[::1]:11434/api/chat",
    ],
)
def test_ollama_acepta_hosts_locales(url):
    motor = MotorOllama(url=url, modelo=MODELO_PRUEBA)

    assert motor._url == url


def test_catalogo_desde_entorno_apaga_todos_los_roles_por_defecto(monkeypatch):
    for variable in (
        "HEIMDALL_MODELO_TEXTO",
        "HEIMDALL_MODELO_ENRUTADOR",
        "HEIMDALL_MODELO_VISION",
        "HEIMDALL_MODELO_OCR",
        "HEIMDALL_MODELO_VOZ",
    ):
        monkeypatch.delenv(variable, raising=False)

    catalogo = crear_catalogo()

    assert isinstance(catalogo, Catalogo)
    assert all(catalogo.obtener(rol) is None for rol in RolModelo)


def test_catalogo_habilita_roles_de_forma_independiente():
    catalogo = crear_catalogo(
        {
            "HEIMDALL_MODELO_TEXTO": " modelo-a ",
            "HEIMDALL_MODELO_ENRUTADOR": "modelo-router",
            "HEIMDALL_MODELO_OCR": "modelo-b",
            "HEIMDALL_MODELO_VISION": " ",
            "HEIMDALL_MODELO_VOZ": "modelo-voz",
        }
    )

    texto = catalogo.obtener(RolModelo.TEXTO)
    enrutador = catalogo.obtener(RolModelo.ENRUTADOR)
    ocr = catalogo.obtener(RolModelo.OCR)
    assert catalogo.obtener(RolModelo.VISION) is None
    voz = catalogo.obtener(RolModelo.VOZ)
    assert texto is not None
    assert enrutador is not None
    assert ocr is not None
    assert voz is not None
    assert texto.nombre == "modelo-a:latest"
    assert enrutador.nombre == "modelo-router:latest"
    assert ocr.nombre == "modelo-b:latest"
    assert voz.nombre == "modelo-voz:latest"


def test_fabrica_planificador_deja_roles_apagados_si_no_hay_modelos():
    planificador = crear_planificador({})

    assert planificador.interpretar(RolModelo.TEXTO, [], []) is None


def test_configuracion_rechaza_valores_desconocidos(monkeypatch):
    monkeypatch.setenv("HEIMDALL_LLM", "api")
    with pytest.raises(ValueError, match="apagado, ollama, nube"):
        crear_motor()


def test_motor_nube_es_un_esqueleto_sin_red_ni_clave():
    with pytest.raises(NotImplementedError):
        MotorNube().interpretar([], [])


def test_frenos_descartan_respuestas_de_baja_confianza(caplog):
    motor = MotorFalso([RespuestaEstructurada("intencion", {}, 0.4)])
    frenos = FrenosLLM(motor, confianza_minima=0.65)
    with caplog.at_level(logging.WARNING, logger="app.llm.frenos"):
        assert frenos.consultar(
            uuid4(),
            [{"role": "user", "content": "contenido_privado"}],
            [],
        ) is None
    assert "confianza insuficiente" in caplog.text.casefold()
    assert "contenido_privado" not in caplog.text


@pytest.mark.parametrize(
    "respuesta",
    [
        SimpleNamespace(),
        SimpleNamespace(confianza="alta"),
        SimpleNamespace(confianza=True),
        SimpleNamespace(confianza=float("nan")),
        SimpleNamespace(confianza=float("inf")),
        SimpleNamespace(confianza=-0.1),
        SimpleNamespace(confianza=1.1),
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


def test_frenos_usan_el_umbral_aprobado_por_defecto():
    aceptable = RespuestaEstructurada("intencion", {}, 0.70)
    baja = RespuestaEstructurada("intencion", {}, 0.69)
    conversacion = uuid4()
    frenos = FrenosLLM(MotorFalso([aceptable, baja]))

    assert frenos.consultar(conversacion, [], []) == aceptable
    assert frenos.consultar(conversacion, [], []) is None


def test_frenos_aplican_limite_por_conversacion():
    respuesta = RespuestaEstructurada("intencion", {}, 0.9)
    motor = MotorFalso([respuesta, respuesta, respuesta])
    frenos = FrenosLLM(motor, max_consultas=2)
    conversacion = uuid4()
    assert frenos.consultar(conversacion, [], []) == respuesta
    assert frenos.consultar(conversacion, [], []) == respuesta
    assert frenos.consultar(conversacion, [], []) is None


def test_frenos_registran_el_limite_de_consultas(caplog):
    respuesta = RespuestaEstructurada("intencion", {}, 0.9)
    frenos = FrenosLLM(MotorFalso([respuesta]), max_consultas=1)
    conversacion = uuid4()
    frenos.consultar(conversacion, [], [])

    with caplog.at_level(logging.WARNING, logger="app.llm.frenos"):
        assert frenos.consultar(conversacion, [], []) is None

    assert "límite de consultas alcanzado" in caplog.text.casefold()


def test_frenos_mantienen_cuotas_separadas_por_conversacion():
    respuesta = RespuestaEstructurada("intencion", {}, 0.9)
    motor = MotorFalso([respuesta, respuesta])
    frenos = FrenosLLM(motor, max_consultas=1)
    assert frenos.consultar(uuid4(), [], []) == respuesta
    assert frenos.consultar(uuid4(), [], []) == respuesta


@pytest.mark.parametrize(
    ("error", "motivo"),
    [
        (OSError("detalle privado"), "OSError"),
        (ErrorRespuestaLLM("detalle privado"), "ErrorRespuestaLLM"),
    ],
)
def test_frenos_registran_errores_del_motor_sin_detalles(error, motivo, caplog):
    motor = MotorQueFalla(error)
    frenos = FrenosLLM(motor, max_consultas=1)
    conversacion_id = uuid4()
    with caplog.at_level(logging.WARNING, logger="app.llm.frenos"):
        assert frenos.consultar(
            conversacion_id,
            [{"role": "user", "content": "contenido_privado"}],
            [],
        ) is None
    assert frenos.consultar(conversacion_id, [], []) is None
    assert motor.llamadas == 1
    assert motivo in caplog.text
    assert "detalle privado" not in caplog.text
    assert "contenido_privado" not in caplog.text


def test_frenos_registran_respuesta_de_tipo_incorrecto(monkeypatch, caplog):
    motor = MotorFalso()
    monkeypatch.setattr(
        motor,
        "interpretar",
        lambda _historial, _herramientas: SimpleNamespace(confianza=0.9),
    )
    frenos = FrenosLLM(motor)

    with caplog.at_level(logging.WARNING, logger="app.llm.frenos"):
        assert frenos.consultar(uuid4(), [], []) is None

    assert "no es RespuestaEstructurada" in caplog.text


@pytest.mark.parametrize(
    "max_consultas,confianza",
    [
        (0, 0.5),
        (1, -0.1),
        (1, 1.1),
        (1, True),
        (1, float("nan")),
        (1, float("inf")),
    ],
)
def test_frenos_validan_configuracion(max_consultas, confianza):
    with pytest.raises(ValueError):
        FrenosLLM(
            MotorFalso([RespuestaEstructurada("intencion", {}, 1)]),
            max_consultas=max_consultas,
            confianza_minima=confianza,
        )
