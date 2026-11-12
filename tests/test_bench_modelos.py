import json
from io import BytesIO
from unittest.mock import patch

import pytest

from scripts.bench_modelos import ejecutar_benchmark


def test_benchmark_envia_solicitud_local_y_extrae_metricas():
    datos = {
        "eval_count": 20,
        "eval_duration": 2_000_000_000,
        "load_duration": 500_000_000,
        "prompt_eval_count": 12,
    }

    with patch(
        "scripts.bench_modelos.urlopen",
        return_value=BytesIO(json.dumps(datos).encode("utf-8")),
    ) as urlopen:
        resultado = ejecutar_benchmark("modelo-prueba", "Hola", 15)

    assert resultado["modelo"] == "modelo-prueba"
    assert resultado["tokens_generados"] == 20
    assert resultado["tokens_por_segundo"] == 10.0
    assert resultado["tokens_prompt"] == 12
    solicitud = json.loads(urlopen.call_args.args[0].data)
    assert urlopen.call_args.args[0].full_url == "http://127.0.0.1:11434/api/chat"
    assert solicitud["model"] == "modelo-prueba"
    assert solicitud["options"] == {"temperature": 0}
    assert solicitud["keep_alive"] == "30m"
    assert urlopen.call_args.kwargs["timeout"] == 15


def test_benchmark_informa_tokens_por_segundo_indefinidos_si_duracion_es_cero():
    datos = {
        "eval_count": 0,
        "eval_duration": 0,
        "load_duration": 0,
        "prompt_eval_count": 0,
    }

    with patch(
        "scripts.bench_modelos.urlopen",
        return_value=BytesIO(json.dumps(datos).encode("utf-8")),
    ):
        resultado = ejecutar_benchmark("modelo-prueba", "Hola", 15)

    assert resultado["tokens_por_segundo"] is None


@pytest.mark.parametrize(
    "modelo,prompt,timeout",
    [
        (" ", "Hola", 15),
        ("modelo", "", 15),
        ("modelo", "Hola", 0),
        ("modelo", "Hola", float("inf")),
    ],
)
def test_benchmark_rechaza_argumentos_invalidos(modelo, prompt, timeout):
    with pytest.raises(ValueError):
        ejecutar_benchmark(modelo, prompt, timeout)


def test_benchmark_rechaza_metricas_invalidas():
    datos = {
        "eval_count": True,
        "eval_duration": 2_000_000_000,
        "load_duration": 500_000_000,
        "prompt_eval_count": 12,
    }

    with patch(
        "scripts.bench_modelos.urlopen",
        return_value=BytesIO(json.dumps(datos).encode("utf-8")),
    ):
        with pytest.raises(ValueError, match="eval_count"):
            ejecutar_benchmark("modelo-prueba", "Hola", 15)
