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
   descarte si la confianza es menor que 0,70 o inválida.
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
10. El catálogo inyectado configura TEXTO, ENRUTADOR, VISION, OCR y VOZ mediante
    nombres explícitos; sin variable, cada rol queda apagado.
11. El planificador serializa la carga en este proceso. Antes de cambiar de
    modelo solicita `keep_alive: 0` y comprueba la lista de Ollama; si no confirma
    la descarga o carga exclusiva, no ejecuta la inferencia.
12. Los plazos monotónicos por rol cubren lock, descarga, carga e inferencia.
    No hay reintentos ni fallback silencioso a nube.

## Modelos y plazos por rol

`crear_catalogo` lee `HEIMDALL_MODELO_TEXTO`,
`HEIMDALL_MODELO_ENRUTADOR`, `HEIMDALL_MODELO_VISION`,
`HEIMDALL_MODELO_OCR` y `HEIMDALL_MODELO_VOZ`. No asigna nombres por defecto;
los roles sin variable quedan apagados y no impiden usar otros roles.
`crear_planificador` usa este catálogo. El selector histórico `HEIMDALL_LLM`
sigue apagado por defecto; al elegir Ollama para el chatbot, también se requiere
un `HEIMDALL_MODELO_TEXTO` explícito.

| Rol | Espera lock | Descarga+verif. | Carga+verif. | Inferencia | Confianza |
|---|---:|---:|---:|---:|---:|
| TEXTO | 150 | 10 | 60 | 45 | 0,70 |
| ENRUTADOR | 150 | 10 | 60 | 15 | 0,70 |
| VISION | 150 | 10 | 60 | 60 | 0,70 |
| OCR | 150 | 10 | 60 | 60 | 0,70 |
| VOZ | 150 | 10 | 60 | 45 | 0,70 |

Los plazos están expresados en segundos; confianza es el umbral mínimo.
Son límites iniciales aprobados, no benchmarks. El plazo de carga de 60 s deja
margen respecto a la única medición aportada de arranque frío (34 s para un
modelo 4B); no representa una garantía para otros modelos o máquinas. La espera
del lock cubre una operación de descarga, carga e inferencia dentro de esos
límites, con margen adicional.

El lock compartido solo coordina planificadores de este proceso. No excluye
otros procesos ni clientes de Ollama; por tanto, la garantía de un modelo
cargado no cubre interferencias externas.

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
