# Entorno local (Windows)

Registro del equipo de desarrollo y de las herramientas instaladas. Se actualiza cuando cambia algo.

## Equipo
| Elemento | Valor |
|---|---|
| RAM | 15,9 GB |
| Tarjeta gráfica | NVIDIA GeForce GTX 1060 6 GB |
| Controlador NVIDIA | 560.94 (Ollama pide 570 o superior para esta tarjeta) |
| Sistema | Windows, PowerShell |

## Herramientas instaladas
| Herramienta | Versión | Uso |
|---|---|---|
| Python (entorno `.venv`) | 3.13 | Proyecto y tests |
| Node.js | 26.13.1 | Necesario para OpenCode |
| npm | 11.20.0 | Instalar OpenCode |
| Ollama | 0.40.16 | Modelos de lenguaje en local |
| OpenCode | 1.19.5 | Asistente de programación en terminal |

## Reparto de uso
- Programar: OpenCode o Copilot, con modelos gratuitos de la nube. No se pegan claves ni datos personales.
- Chatbot de heimdall: Ollama en local (la salida estructurada con esquema JSON no funciona en la nube de Ollama).

## Incidencia: Ollama falla con la tarjeta
- Síntoma: `ollama run` devuelve error 500, `llama-server` se cierra con `0xc0000409` y `CUDA error: the provided PTX was compiled with an unsupported toolchain`.
- Causa probable: controlador NVIDIA anterior al 570 con una tarjeta Pascal.
- Solución definitiva: actualizar el controlador y reiniciar.
- Alternativa mientras tanto: arrancar el servidor sin CUDA para que use Vulkan o el procesador.

        $env:CUDA_VISIBLE_DEVICES = "-1"
        ollama serve

  Con esa variable, el registro del servidor detectó la tarjeta por Vulkan (6,1 GiB totales).
- Estado: confirmado el 2026-11-12. `llama3.2:3b` responde con `100% GPU` por Vulkan (2,6 GB, contexto 4096). La primera carga tarda unos 25 s. Hay que exportar la variable antes de cada `ollama serve`; el controlador sigue en 560.94.

El chatbot precarga Ollama al arrancar. El calentamiento permite 30 s como
mínimo para cubrir la primera carga; las consultas normales tienen un timeout
de 10 s, configurable con `HEIMDALL_LLM_TIMEOUT` (segundos).

## Arranque rápido
1. Abrir VS Code en la carpeta del proyecto y activar `.venv`.
2. Recargar el PATH si una terminal nueva no reconoce `node`, `npm` o `ollama`.
3. Servidor de Ollama en su propia terminal; las pruebas, en otra.