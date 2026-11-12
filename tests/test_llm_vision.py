import json
import struct
import zlib
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest

from app.llm.interfaz import ErrorRespuestaLLM, RespuestaEstructurada
from app.llm.planificador import PlanificadorModelos
from app.llm.roles import Catalogo, RolModelo
from app.llm.vision import (
    ErrorImagen,
    MotorOllamaVision,
    MotorVisionFalso,
    validar_imagen,
)


def _png(ancho=1, alto=1, relleno=b"") -> bytes:
    def chunk(tipo, datos):
        return (
            struct.pack(">I", len(datos))
            + tipo
            + datos
            + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">II", ancho, alto) + b"\x08\x06\x00\x00\x00")
        + chunk(b"IDAT", zlib.compress(b"\x00") + relleno)
        + chunk(b"IEND", b"")
    )


def _jpeg(ancho=1, alto=1) -> bytes:
    return (
        b"\xff\xd8\xff\xc0"
        + struct.pack(">H", 17)
        + b"\x08"
        + struct.pack(">HH", alto, ancho)
        + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
        + b"\xff\xd9"
    )


def _guardar(tmp_path: Path, contenido: bytes, nombre="imagen.png") -> Path:
    ruta = tmp_path / nombre
    ruta.write_bytes(contenido)
    return ruta


@pytest.mark.parametrize("contenido", [_png(), _jpeg()])
def test_acepta_jpeg_y_png_locales(tmp_path, contenido):
    ruta = _guardar(tmp_path, contenido)

    assert validar_imagen(ruta) == contenido


@pytest.mark.parametrize(
    "contenido",
    [b"", b"imagen", b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff\xc0\x00\x01"],
)
def test_rechaza_archivos_vacios_o_no_validos(tmp_path, contenido):
    ruta = _guardar(tmp_path, contenido)

    with pytest.raises(ErrorImagen):
        validar_imagen(ruta)


@pytest.mark.parametrize(
    "ancho,alto",
    [(4097, 1), (1, 4097), (0, 1), (1, 0)],
)
def test_rechaza_dimensiones_fuera_de_limite(tmp_path, ancho, alto):
    ruta = _guardar(tmp_path, _png(ancho, alto))

    with pytest.raises(ErrorImagen, match="dimensiones|4096"):
        validar_imagen(ruta)


def test_acepta_dimensiones_maximas(tmp_path):
    ruta = _guardar(tmp_path, _png(4096, 4096))

    assert validar_imagen(ruta) == _png(4096, 4096)


def test_rechaza_archivos_mayores_de_5_mb(tmp_path):
    ruta = _guardar(tmp_path, _png(relleno=b"x" * 5_000_000))

    with pytest.raises(ErrorImagen, match="5 MB"):
        validar_imagen(ruta)


def test_acepta_archivo_de_hasta_5_mb(tmp_path):
    relleno = b"x" * (5_000_000 - len(_png()))
    ruta = _guardar(tmp_path, _png(relleno=relleno))

    assert len(validar_imagen(ruta)) == 5_000_000


def test_rechaza_enlace_simbolico(tmp_path):
    destino = _guardar(tmp_path, _png(), "destino.png")
    enlace = tmp_path / "enlace.png"
    try:
        enlace.symlink_to(destino)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"El sistema no permite crear enlaces simbólicos: {error}")

    with pytest.raises(ErrorImagen, match="simbólicos"):
        validar_imagen(enlace)


def test_motor_falso_valida_y_devuelve_respuesta_prefijada(tmp_path):
    ruta = _guardar(tmp_path, _png())
    respuesta = RespuestaEstructurada("leer_imagen", {"texto": "hola"}, 0.9)
    motor = MotorVisionFalso([respuesta])

    assert motor.interpretar_imagen(ruta, "Lee el texto") == respuesta
    assert motor.imagenes == [ruta]
    assert motor.instrucciones == ["Lee el texto"]


def test_motor_ollama_envia_imagen_y_lee_salida_estructurada(tmp_path):
    ruta = _guardar(tmp_path, _png())
    datos = {"intencion": "leer_imagen", "campos": {"texto": "hola"}, "confianza": 0.9}
    respuesta_http = {"message": {"content": json.dumps(datos)}}
    motor = MotorOllamaVision(modelo="modelo-vision")

    with patch(
        "app.llm.vision.urlopen",
        return_value=BytesIO(json.dumps(respuesta_http).encode("utf-8")),
    ) as urlopen:
        respuesta = motor.interpretar_imagen(ruta, "Lee el texto")

    assert respuesta == RespuestaEstructurada(**datos)
    solicitud = json.loads(urlopen.call_args.args[0].data)
    assert solicitud["messages"][0]["content"] == "Lee el texto"
    assert solicitud["messages"][0]["images"]
    assert solicitud["options"] == {"temperature": 0}
    assert solicitud["keep_alive"] == "30m"


def test_motor_ollama_rechaza_respuesta_estructurada_invalida(tmp_path):
    ruta = _guardar(tmp_path, _png())
    motor = MotorOllamaVision(modelo="modelo-vision")

    with patch(
        "app.llm.vision.urlopen",
        return_value=BytesIO(b'{"message":{"content":"{}"}}'),
    ):
        with pytest.raises(ErrorRespuestaLLM, match="esquema"):
            motor.interpretar_imagen(ruta, "Lee el texto")


def test_planificador_usa_rol_vision_con_motor_falso(tmp_path):
    ruta = _guardar(tmp_path, _png())
    llamadas = []
    respuesta = RespuestaEstructurada("leer_imagen", {}, 0.9)

    class MotorFalso:
        def modelos_cargados(self, timeout):
            llamadas.append(("modelos", timeout))
            return ("modelo-vision",)

        def calentar(self, timeout=None):
            raise AssertionError("El modelo ya está cargado.")

        def descargar(self, timeout, modelo=None):
            raise AssertionError("No debe descargar.")

        def interpretar(self, historial, herramientas):
            raise AssertionError("Debe interpretar imagen.")

        def interpretar_imagen(self, imagen, instruccion):
            llamadas.append(("imagen", imagen, instruccion))
            return respuesta

    planificador = PlanificadorModelos(
        Catalogo({RolModelo.VISION: "modelo-vision"}),
        lambda configuracion: MotorFalso(),
    )

    assert planificador.interpretar_imagen(
        RolModelo.VISION, ruta, "Describe"
    ) == respuesta
    assert ("imagen", ruta, "Describe") in llamadas


def test_planificador_rechaza_roles_que_no_son_de_imagen(tmp_path):
    planificador = PlanificadorModelos(Catalogo({}))

    with pytest.raises(ValueError, match="VISION u OCR"):
        planificador.interpretar_imagen(RolModelo.TEXTO, tmp_path / "imagen.png", "")


def test_planificador_valida_antes_de_crear_motor(tmp_path):
    creada = False

    def fabrica(_configuracion):
        nonlocal creada
        creada = True
        raise AssertionError("No debe crear un motor para una imagen inválida.")

    planificador = PlanificadorModelos(
        Catalogo({RolModelo.VISION: "modelo-vision"}),
        fabrica,
    )

    with pytest.raises(ErrorImagen):
        planificador.interpretar_imagen(
            RolModelo.VISION,
            _guardar(tmp_path, b"no es imagen"),
            "Describe",
        )

    assert not creada
