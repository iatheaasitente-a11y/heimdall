import wave
from pathlib import Path

import pytest

from app.llm.voz import ErrorAudio, MotorOllamaVoz, MotorVozFalso, validar_audio


def _crear_wav(ruta: Path, duracion=1, frecuencia=8000) -> Path:
    fotogramas = int(duracion * frecuencia)
    with wave.open(str(ruta), "wb") as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(2)
        archivo.setframerate(frecuencia)
        archivo.writeframes(b"\x00\x00" * fotogramas)
    return ruta


def test_valida_wav_y_calcula_duracion(tmp_path):
    ruta = _crear_wav(tmp_path / "voz.wav", 2)

    assert validar_audio(ruta) == 2


def test_acepta_el_limite_de_300_segundos(tmp_path):
    ruta = _crear_wav(tmp_path / "voz.wav", 300)

    assert validar_audio(ruta) == 300


def test_rechaza_audio_de_mas_de_300_segundos(tmp_path):
    ruta = _crear_wav(tmp_path / "voz.wav", 300.1)

    with pytest.raises(ErrorAudio, match="300 segundos"):
        validar_audio(ruta)


def test_rechaza_archivo_mayor_de_20_mb_antes_de_leerlo(tmp_path):
    ruta = tmp_path / "voz.wav"
    ruta.write_bytes(b"x" * 20_000_001)

    with pytest.raises(ErrorAudio, match="20 MB"):
        validar_audio(ruta)


@pytest.mark.parametrize("contenido", [b"", b"audio", b"RIFF\x00\x00\x00\x00WAVE"])
def test_rechaza_archivos_que_no_son_wav_validos(tmp_path, contenido):
    ruta = tmp_path / "voz.wav"
    ruta.write_bytes(contenido)

    with pytest.raises(ErrorAudio, match="WAV PCM"):
        validar_audio(ruta)


def test_rechaza_enlace_simbolico(tmp_path):
    destino = _crear_wav(tmp_path / "destino.wav")
    enlace = tmp_path / "enlace.wav"
    try:
        enlace.symlink_to(destino)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"El sistema no permite crear enlaces simbólicos: {error}")

    with pytest.raises(ErrorAudio, match="simbólicos"):
        validar_audio(enlace)


def test_motor_falso_valida_audio_y_devuelve_transcripcion(tmp_path):
    ruta = _crear_wav(tmp_path / "voz.wav")
    motor = MotorVozFalso(["hola"])

    assert motor.transcribir(ruta) == "hola"
    assert motor.audios == [ruta]


def test_motor_falso_sin_respuestas_lanza_error(tmp_path):
    ruta = _crear_wav(tmp_path / "voz.wav")

    with pytest.raises(RuntimeError, match="no tiene transcripciones"):
        MotorVozFalso([]).transcribir(ruta)


def test_motor_ollama_esqueleto_no_intenta_transcribir(tmp_path):
    ruta = _crear_wav(tmp_path / "voz.wav")

    with pytest.raises(NotImplementedError, match="pendiente"):
        MotorOllamaVoz().transcribir(ruta)
