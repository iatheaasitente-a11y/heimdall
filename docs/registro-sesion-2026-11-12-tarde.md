# Registro de sesion - 2026-11-12 (tarde)

## Contexto de inicio

- Rama de partida: `refactor/unificar-duplicados` (push a origin).
- Se creo `docs/mejoras-agenda.md` con el estado de la agenda y 8 mejoras pendientes.
- Se creo la rama `feat/validador-llm` desde ahi.

## Commits de la sesion

| # | Commit | Que hizo |
|---|---|---|
| 1 | `3b6510f` docs: resumen de mejoras de agenda y roadmap | Creo `docs/mejoras-agenda.md` |
| 2 | `c140e13` feat: validador LLM para acciones sensibles | Creo `app/llm/validador.py` + 3 tests |
| 3 | `93998ed` feat agendado paso a paso | Creo `app/agents/agenda_paso_a_paso.py` + tests + conexion en `personal.py` |
| 4 | `fefa656` docs estado de mejoras de agenda | Actualizo `docs/mejoras-agenda.md` (mejora 1 hecha) |
| 5 | `f43de4f` docs consolidar documentacion viva | Movo 17 docs a `docs/historico/` |
| 6 | `docs registro sesion tarde y proximos pasos` | Creo este registro |

## Problemas resueltos

- BOM (`\ufeff`): `Set-Content -Encoding UTF8` en Windows PowerShell anade BOM y Python lo rechaza. Solucion: `System.IO.File::WriteAllText` con `UTF8Encoding($false)`.
- Here-strings truncados: al pegar bloques largos, PowerShell perdia lineas (regex, llaves). Solucion: base64 + `FromBase64String`, o parches pequenos y targeted.
- Orden de reglas vs paso-a-paso: al principio el modulo de paso a paso interceptaba antes que `ReglasDeterministas` y rompia los flujos de un solo mensaje. Solucion: mover la llamada despues de `resultado_regla`.
- Ruta relativa en .NET: `WriteAllText` con ruta relativa resolvia contra `C:\Users\alvaro`. Solucion: `Join-Path (Get-Location).Path`.

## Estado al cerrar

- Rama: `feat/validador-llm`.
- Tests: 824 passed.
- Todo pushado a `origin/feat/validador-llm`.
- Raiz limpia (sin `reglas_respaldo.py`, `reparar_init.py`, `heimdall.db`, caches).
- Docs consolidados: 4 vivos (`README.md`, `arquitectura.md`, `hoja-de-ruta.md`, `decisiones.md`) + `docs/historico/`.

## Proxima sesion

1. Revisar `docs/mejoras-agenda.md` (mejora 1 hecha, 2-8 pendientes).
2. Empezar mejora 2: recordatorio automatico al crear cita.
3. Despues: mejoras 3-8 una a una, cada una con rama, tests y commit.
4. Cuando la agenda este cerrada: chatbot funcional con Ollama real.
5. Luego: avisos reales, panel Streamlit, Telegram y oficina virtual de agentes.