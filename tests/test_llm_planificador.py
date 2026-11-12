import json
from io import BytesIO
from threading import Lock
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch

import pytest

from app.llm.interfaz import ErrorRespuestaLLM, RespuestaEstructurada
from app.llm.planificador import PlanificadorModelos
from app.llm.roles import Catalogo, PoliticaRol, RolModelo
from app.llm.vision import validar_imagen


class MotorLocalFalso:
    def __init__(
        self,
        nombre,
        cargados,
        llamadas,
        respuesta,
        reloj=lambda: 0.0,
        descargar=True,
        cargar=True,
    ):
        self.nombre = nombre
        self.cargados = cargados
        self.llamadas = llamadas
        self.respuesta = respuesta
        self.reloj = reloj
        self.descargar_habilitado = descargar
        self.cargar_habilitado = cargar

    def modelos_cargados(self, timeout):
        self.llamadas.append(("listar", timeout))
        return tuple(sorted(self.cargados))

    def descargar(self, timeout, modelo=None):
        self.llamadas.append(("descargar", modelo, timeout))
        if self.descargar_habilitado:
            self.cargados.discard(modelo)

    def calentar(self, timeout=None):
        self.llamadas.append(("cargar", self.nombre, timeout))
        if self.cargar_habilitado:
            self.cargados.add(self.nombre)
        self.reloj.avanzar(self.reloj.duracion_carga)

    def interpretar(self, historial, herramientas):
        self.llamadas.append(("inferir", self.nombre))
        self.reloj.avanzar(self.reloj.duracion_inferencia)
        return self.respuesta

    def interpretar_imagen(self, imagen, instruccion):
        self.llamadas.append(("inferir_imagen", self.nombre, instruccion))
        validar_imagen(imagen)
        self.reloj.avanzar(self.reloj.duracion_inferencia)
        return self.respuesta


class RelojFalso:
    def __init__(self):
        self.valor = 0.0
        self.duracion_carga = 0.0
        self.duracion_inferencia = 0.0

    def __call__(self):
        return self.valor

    def avanzar(self, segundos):
        self.valor += segundos


def _crear_planificador(
    modelos,
    cargados=None,
    *,
    respuesta=None,
    reloj=None,
    descargar=True,
    cargar=True,
    politicas=None,
    cerrojo=None,
):
    llamadas = []
    estado = set(cargados or ())
    reloj = RelojFalso() if reloj is None else reloj

    def fabrica(configuracion):
        return MotorLocalFalso(
            configuracion.nombre,
            estado,
            llamadas,
            respuesta
            or RespuestaEstructurada("intencion", {"id": str(uuid4())}, 0.9),
            reloj,
            descargar,
            cargar,
        )

    planificador = PlanificadorModelos(
        Catalogo(modelos, politicas),
        fabrica,
        reloj,
        cerrojo,
    )
    return planificador, estado, llamadas, reloj


def test_rol_apagado_no_crea_motor_ni_afecta_otro_rol():
    planificador, cargados, llamadas, _ = _crear_planificador(
        {RolModelo.TEXTO: "modelo-texto"}
    )

    assert planificador.interpretar(RolModelo.OCR, [], []) is None
    respuesta = planificador.interpretar(RolModelo.TEXTO, [], [])

    assert respuesta is not None
    assert cargados == {"modelo-texto"}
    assert any(llamada[0] == "inferir" for llamada in llamadas)


def test_carga_infiere_y_aplica_timeout_del_rol():
    planificador, _, llamadas, _ = _crear_planificador(
        {RolModelo.ENRUTADOR: "modelo-router"}
    )

    respuesta = planificador.interpretar(RolModelo.ENRUTADOR, [], [])

    assert respuesta is not None
    assert ("cargar", "modelo-router", 60) in llamadas
    assert ("inferir", "modelo-router") in llamadas


def test_fabrica_por_defecto_pasa_timeouts_del_rol_sin_red():
    contenido = {
        "message": {
            "content": json.dumps(
                {"intencion": "resumen", "campos": {}, "confianza": 0.9}
            )
        }
    }
    respuestas = [
        BytesIO(b'{"models":[]}'),
        BytesIO(b"{}"),
        BytesIO(b'{"models":[{"name":"modelo-ocr"}]}'),
        BytesIO(json.dumps(contenido).encode("utf-8")),
    ]
    planificador = PlanificadorModelos(
        Catalogo({RolModelo.OCR: "modelo-ocr"}),
    )

    with patch("app.llm.ollama.urlopen", side_effect=respuestas) as urlopen:
        resultado = planificador.interpretar(RolModelo.OCR, [], [])

    assert resultado == RespuestaEstructurada("resumen", {}, 0.9)
    assert urlopen.call_count == 4
    assert urlopen.call_args_list[0].kwargs["timeout"] == 10
    assert urlopen.call_args_list[1].kwargs["timeout"] == 60
    assert 0 < urlopen.call_args_list[2].kwargs["timeout"] <= 60
    assert urlopen.call_args_list[3].kwargs["timeout"] == 60
    solicitud_carga = json.loads(urlopen.call_args_list[1].args[0].data)
    solicitud_inferencia = json.loads(urlopen.call_args_list[3].args[0].data)
    assert solicitud_carga["model"] == "modelo-ocr"
    assert solicitud_inferencia["model"] == "modelo-ocr"


def test_planificador_descarga_y_verifica_antes_de_cargar_otro_modelo():
    respuesta = {
        "message": {
            "content": json.dumps(
                {"intencion": "resumen", "campos": {}, "confianza": 0.9}
            )
        }
    }
    respuestas = [
        BytesIO(b'{"models":[{"name":"modelo-anterior"}]}'),
        BytesIO(b"{}"),
        BytesIO(b'{"models":[]}'),
        BytesIO(b"{}"),
        BytesIO(b'{"models":[{"name":"modelo-ocr"}]}'),
        BytesIO(json.dumps(respuesta).encode("utf-8")),
    ]
    planificador = PlanificadorModelos(
        Catalogo({RolModelo.OCR: "modelo-ocr"}),
    )

    with patch("app.llm.ollama.urlopen", side_effect=respuestas) as urlopen:
        resultado = planificador.interpretar(RolModelo.OCR, [], [])

    assert resultado == RespuestaEstructurada("resumen", {}, 0.9)
    assert urlopen.call_count == 6
    llamadas = [llamada.args[0] for llamada in urlopen.call_args_list]
    assert [llamada.get_method() for llamada in llamadas] == [
        "GET",
        "POST",
        "GET",
        "POST",
        "GET",
        "POST",
    ]
    assert llamadas[1].full_url.endswith("/api/generate")
    assert json.loads(llamadas[1].data) == {
        "model": "modelo-anterior",
        "keep_alive": 0,
        "stream": False,
    }
    assert json.loads(llamadas[3].data)["model"] == "modelo-ocr"
    assert json.loads(llamadas[5].data)["model"] == "modelo-ocr"


def test_reutiliza_modelo_ya_cargado_sin_descargarlo():
    planificador, _, llamadas, _ = _crear_planificador(
        {RolModelo.TEXTO: "modelo-texto"},
        {"modelo-texto"},
    )

    assert planificador.interpretar(RolModelo.TEXTO, [], []) is not None

    assert not any(llamada[0] in {"cargar", "descargar"} for llamada in llamadas)


def test_descarga_y_verifica_el_modelo_anterior_antes_de_cargar_otro():
    planificador, _, llamadas, _ = _crear_planificador(
        {
            RolModelo.TEXTO: "modelo-texto",
            RolModelo.OCR: "modelo-ocr",
        },
        {"modelo-anterior"},
    )

    assert planificador.interpretar(RolModelo.TEXTO, [], []) is not None
    llamadas.clear()
    assert planificador.interpretar(RolModelo.OCR, [], []) is not None

    descarga = next(i for i, llamada in enumerate(llamadas) if llamada[0] == "descargar")
    carga = next(i for i, llamada in enumerate(llamadas) if llamada[0] == "cargar")
    listado_tras_descarga = next(
        i for i, llamada in enumerate(llamadas[descarga + 1 :], descarga + 1)
        if llamada[0] == "listar"
    )
    assert descarga < listado_tras_descarga < carga


def test_falla_cerrado_si_no_se_confirma_descarga_del_modelo_anterior():
    planificador, cargados, llamadas, _ = _crear_planificador(
        {RolModelo.TEXTO: "modelo-nuevo"},
        {"modelo-anterior"},
        descargar=False,
    )

    with pytest.raises(ErrorRespuestaLLM, match="confirmar la descarga"):
        planificador.interpretar(RolModelo.TEXTO, [], [])

    assert cargados == {"modelo-anterior"}
    assert not any(llamada[0] == "cargar" for llamada in llamadas)
    assert not any(llamada[0] == "inferir" for llamada in llamadas)


def test_falla_cerrado_si_no_se_confirma_la_carga_exclusiva():
    planificador, cargados, llamadas, _ = _crear_planificador(
        {RolModelo.TEXTO: "modelo-nuevo"},
        cargar=False,
    )

    with pytest.raises(ErrorRespuestaLLM, match="carga exclusiva"):
        planificador.interpretar(RolModelo.TEXTO, [], [])

    assert cargados == set()
    assert not any(llamada[0] == "inferir" for llamada in llamadas)


@pytest.mark.parametrize(
    "confianza",
    [None, "alta", True, float("nan"), float("inf"), -0.1, 1.1],
)
def test_respuesta_con_confianza_invalida_se_descarta(confianza):
    respuesta = SimpleNamespace(confianza=confianza)
    planificador, _, _, _ = _crear_planificador(
        {RolModelo.TEXTO: "modelo-texto"},
        respuesta=respuesta,
    )

    assert planificador.interpretar(RolModelo.TEXTO, [], []) is None


def test_respuesta_sin_confianza_se_descarta():
    planificador, _, _, _ = _crear_planificador(
        {RolModelo.TEXTO: "modelo-texto"},
        respuesta=SimpleNamespace(),
    )

    assert planificador.interpretar(RolModelo.TEXTO, [], []) is None


def test_timeout_monotonico_de_carga_impide_la_inferencia():
    reloj = RelojFalso()
    reloj.duracion_carga = 61
    planificador, _, llamadas, _ = _crear_planificador(
        {RolModelo.TEXTO: "modelo-texto"},
        reloj=reloj,
    )

    with pytest.raises(TimeoutError, match="carga"):
        planificador.interpretar(RolModelo.TEXTO, [], [])

    assert not any(llamada[0] == "inferir" for llamada in llamadas)


def test_timeout_monotonico_de_inferencia_se_propaga():
    reloj = RelojFalso()
    reloj.duracion_inferencia = 46
    planificador, _, _, _ = _crear_planificador(
        {RolModelo.TEXTO: "modelo-texto"},
        {"modelo-texto"},
        reloj=reloj,
    )

    with pytest.raises(TimeoutError, match="inferencia"):
        planificador.interpretar(RolModelo.TEXTO, [], [])


def test_lock_se_libera_si_el_motor_lanza_error():
    cerrojo = Lock()
    planificador, _, _, _ = _crear_planificador(
        {RolModelo.TEXTO: "modelo-texto"},
        {"modelo-texto"},
        cerrojo=cerrojo,
    )

    def fallar(_historial, _herramientas):
        raise OSError("ollama no disponible")

    planificador._fabrica_motor = lambda configuracion: SimpleNamespace(
        modelos_cargados=lambda timeout: ("modelo-texto",),
        calentar=lambda timeout=None: None,
        descargar=lambda timeout, modelo=None: None,
        interpretar=fallar,
    )

    with pytest.raises(OSError, match="no disponible"):
        planificador.interpretar(RolModelo.TEXTO, [], [])

    assert cerrojo.acquire(blocking=False)
    cerrojo.release()


def test_timeout_al_adquirir_lock_no_consulta_ollama():
    cerrojo = Lock()
    cerrojo.acquire()
    politica = PoliticaRol(0.01, 10, 60, 45, 0.70)
    planificador, _, llamadas, _ = _crear_planificador(
        {RolModelo.TEXTO: "modelo-texto"},
        politicas={RolModelo.TEXTO: politica},
        cerrojo=cerrojo,
    )
    try:
        with pytest.raises(TimeoutError, match="espera"):
            planificador.interpretar(RolModelo.TEXTO, [], [])
    finally:
        cerrojo.release()

    assert llamadas == []
