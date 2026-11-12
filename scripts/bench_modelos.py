"""Mide una inferencia de texto en una instancia local de Ollama."""

import argparse
import json
import math
import time
from urllib.request import Request, urlopen

URL_OLLAMA = "http://127.0.0.1:11434/api/chat"
NANOSEGUNDOS_POR_SEGUNDO = 1_000_000_000


def ejecutar_benchmark(modelo: str, prompt: str, timeout: float) -> dict[str, object]:
    """Ejecuta una solicitud de texto y extrae métricas informadas por Ollama.

    Raises:
        ValueError: Si los argumentos o las métricas de respuesta son inválidos.
        OSError: Si Ollama no está disponible o falla la solicitud.
    """
    modelo = _texto_no_vacio(modelo, "El modelo")
    prompt = _texto_no_vacio(prompt, "El prompt")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ValueError("El timeout debe ser positivo y finito.")

    solicitud = Request(
        URL_OLLAMA,
        data=json.dumps(
            {
                "model": modelo,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0},
                "keep_alive": "30m",
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    inicio = time.perf_counter()
    with urlopen(solicitud, timeout=timeout) as respuesta_http:
        respuesta = json.loads(respuesta_http.read().decode("utf-8"))
    duracion_total = time.perf_counter() - inicio
    return _extraer_metricas(modelo, respuesta, duracion_total)


def _extraer_metricas(
    modelo: str,
    respuesta: object,
    duracion_total: float,
) -> dict[str, object]:
    """Valida las métricas de Ollama y calcula los tokens por segundo."""
    if not isinstance(respuesta, dict):
        raise ValueError("Ollama devolvió una respuesta inválida.")
    tokens_generados = _entero_no_negativo(respuesta.get("eval_count"), "eval_count")
    duracion_inferencia = _entero_no_negativo(
        respuesta.get("eval_duration"),
        "eval_duration",
    )
    carga = _entero_no_negativo(respuesta.get("load_duration"), "load_duration")
    tokens_prompt = _entero_no_negativo(
        respuesta.get("prompt_eval_count"),
        "prompt_eval_count",
    )
    tokens_por_segundo = (
        tokens_generados / (duracion_inferencia / NANOSEGUNDOS_POR_SEGUNDO)
        if duracion_inferencia
        else None
    )
    return {
        "modelo": modelo,
        "duracion_total_s": round(duracion_total, 3),
        "carga_s": round(carga / NANOSEGUNDOS_POR_SEGUNDO, 3),
        "tokens_prompt": tokens_prompt,
        "tokens_generados": tokens_generados,
        "tokens_por_segundo": (
            round(tokens_por_segundo, 2)
            if tokens_por_segundo is not None
            else None
        ),
    }


def _entero_no_negativo(valor: object, campo: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise ValueError(f"Ollama devolvió una métrica inválida: {campo}.")
    return valor


def _texto_no_vacio(valor: str, nombre: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nombre} no puede estar vacío.")
    return valor.strip()


def main() -> None:
    """Ejecuta la CLI y muestra las métricas en JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelo", required=True, help="Nombre exacto del modelo local.")
    parser.add_argument("--prompt", required=True, help="Prompt de prueba.")
    parser.add_argument(
        "--timeout",
        required=True,
        type=float,
        help="Tiempo máximo de espera en segundos.",
    )
    argumentos = parser.parse_args()
    metricas = ejecutar_benchmark(
        argumentos.modelo,
        argumentos.prompt,
        argumentos.timeout,
    )
    print(json.dumps(metricas, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
