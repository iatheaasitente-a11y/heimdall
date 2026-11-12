# Plan maestro de Heimdall

## Estado actual

### Fase 1 completada - 12 de noviembre de 2026

- Consulta de agenda por lenguaje natural.
- Respuesta natural del resumen diario en Telegram.
- Conversacion basica sin depender del LLM.
- Diagnostico de Ollama sin exponer datos sensibles.
- Timeout ampliado para el arranque del modelo.
- Suite de pruebas en verde: 780 tests.

## Siguiente fase: crear eventos

Objetivo: permitir crear una cita desde Telegram mediante lenguaje natural.

Ejemplo:

```text
crea un evento dentista manana a las 10 durante 1 hora
```

Comportamiento esperado:

1. Detectar la intencion de crear un evento.
2. Extraer titulo, fecha, hora y duracion.
3. Pedir unicamente los datos que falten.
4. Mostrar una propuesta clara antes de guardar.
5. Crear el evento solo tras confirmacion del usuario.
6. Confirmar la creacion con fecha y hora en espanol.
