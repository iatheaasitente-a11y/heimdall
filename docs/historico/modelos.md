# Banco de modelos por rol

Plantilla vacía para registrar mediciones reproducibles. No contiene
benchmarks ejecutados ni modelos recomendados.

## Protocolo

1. Anotar equipo, sistema operativo, backend, versión de Ollama y límites de
   memoria de GPU.
2. Ejecutar un solo modelo a la vez y anotar el rol y la tarea exacta.
3. Registrar por separado la primera inferencia y las inferencias calientes.
4. Conservar el prompt, el conjunto de prueba y la versión de sus datos.
5. No comparar cifras obtenidas con protocolos o equipos distintos.

Para una medición básica de texto, usar `scripts/bench_modelos.py` indicando
modelo, prompt y timeout. La primera llamada puede incluir la carga del modelo;
la duración de carga y la tasa de generación se informan por separado. El
script solo consulta la instancia local de Ollama en `127.0.0.1`; no descarga
modelos. Detener el chatbot y otras cargas de Ollama durante una comparación.

## Resultados

| Fecha | Equipo/backend | Rol | Modelo | Contexto | Carga fría (s) | Inferencia caliente (s) | Tokens/s | VRAM | Prueba/calidad | Notas |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|
|  |  |  |  |  |  |  |  |  |  |  |
