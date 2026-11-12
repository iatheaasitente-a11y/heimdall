# Plan: conectar un LLM a la estructura

Principio: el modelo interpreta, Python calcula, SQLite conserva. El modelo no
escribe números ni fechas.

## Reglas de diseño

1. El LLM devuelve solo datos estructurados (intención, campos, confianza),
   nunca la respuesta final con cifras.
2. Reglas primero; el LLM solo entra donde las reglas no llegan.
3. Apagado por defecto. Si falla o no está disponible, el sistema sigue con las
   reglas.
4. Frenos: timeout sin reintentos, tope de consultas por conversación y
   descarte si la confianza es baja.
5. La configuración actual permite LLM apagado, Ollama o el esqueleto nube;
   no hay proveedor de nube configurado.
6. El `usuario_id` lo pone el sistema, nunca el modelo.
7. Las reglas temporales usan un parser puro con reloj/zona recibidos como
   argumentos; un valor ambiguo se aclara en vez de completarse por intuición.
8. La respuesta se valida contra el catálogo después del motor; confianza
   ausente o ilegible es baja. El contexto incluye los últimos cuatro turnos y
   la aclaración pendiente, si existe.
9. El banco de frases tiene 70 ejemplos de ajuste y 30 de reserva. La medición
   de reglas fase 12 obtuvo 21/70 (30,0 %) y 9/30 (30,0 %) resultados correctos,
   respectivamente, sin ajustar reglas con la reserva.

## Fases siguientes

### Bloque A — Chatbot funcional

| Fase | Objetivo | Criterio de terminado | Dependencias |
|---|---|---|---|
| A1. Integración | Integrar la cadena completa de fases 1–13 en una rama de entrega. | Checkout limpio con cadena integrada y `pytest -q`, importaciones y calidad en verde. | Fases 1–13 confirmadas. |
| A2. Comparación de motores | Medir Ollama `llama3.2:3b` y `qwen3:4b-instruct-2507` en la GTX 1060 con el mismo guion. | Publicar resultados observados para comprensión, aclaraciones, latencia fría/caliente y consumo; seleccionar un motor con evidencia. | A1; servidor Ollama y modelos instalados; selección de modelo accesible desde el chatbot. |
| A3. Criterio funcional | Probar el recorrido terminal, reglas primero, persistencia y fallback del LLM. | Mantener como referencia la fase 12: 21/70 y 9/30 resultados correctos (30,0 % por conjunto), más todas las pruebas manuales de [`prueba-real.md`](./prueba-real.md). | A1 y A2. |

### Bloque B — Ampliaciones posteriores

| Fase | Objetivo | Criterio de terminado | Dependencias |
|---|---|---|---|
| B1. Programador de avisos | Enviar recordatorios vencidos mediante un adaptador de notificación. | Envío único, errores observables y cobertura de pruebas con transporte falso. | Bloque A; servicios de recordatorios. |
| B2. NBA real | Implementar una fuente de datos real detrás de `FuenteNBA`. | Pruebas del contrato, errores explícitos y credenciales gestionadas fuera del código. | Bloque A; proveedor seleccionado. |
| B3. Panel Streamlit | Añadir las pestañas Chat, Hoy, Hábitos, Objetivos y Conversaciones. | Operaciones delegadas en servicios y ninguna acción de borrado en la interfaz. | Bloque A; composición disponible. |
| B4. Telegram | Añadir un adaptador de Telegram sobre el router/agente existente. | Transporte aislado, identidad validada y pruebas sin red ni credenciales. | Bloque A; política de identidad definida. |
| B5. Aviso de cámara | Exponer el aviso de cámara mediante una herramienta. | Esquema, autorización, delegación y envío cubiertos por pruebas. | Bloque A; evento y canal de aviso definidos. |

La guía reproducible de la prueba manual está en
[`prueba-real.md`](./prueba-real.md). El historial y validación de cada fase se
registran en [`revision-fases.md`](./revision-fases.md).
