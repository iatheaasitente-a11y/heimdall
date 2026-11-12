# Hoja de ruta

## Pasos
1. Clases de dominio — hecho
2. Relaciones — hecho
3. Serialización y esquemas Pydantic — hecho
4. Tablas SQL (SQLite) — hecho (esquema, conexión e inicialización)
5. Repositorios — hecho (todas las entidades)
6. Servicios — hecho (Usuarios, Agenda, Recordatorios, Hábitos, Objetivos y
   Conversaciones)
7. Clase abstracta del agente — pendiente
8. Agentes concretos (personal) — hecho; NBA, pendiente
9. Fábrica y router — pendiente
10. Chatbot (herramientas, interfaz) — pendiente

Fuera de alcance por ahora: FastAPI, Telegram y una fuente real de datos NBA.

## Auditoría de Hugin

Hecha en `docs/auditoria-hugin.md`. No se porta código fuente completo; las
ideas de fechas, reglas deterministas y evaluación de frases se adaptan en
fases separadas. Memoria/RAG, persistencia alternativa, avisos operativos,
copias, sincronización y canales empresariales quedan descartados.

## Lenguaje temporal

Hecho: `app/domain/lenguaje_fechas.py` resuelve fechas hacia delante, acepta
ayer y anteayer solo con `permitir_pasado=True`, y marca las horas sin franja
como no acotadas para que el agente pueda pedir aclaración.

## Herramientas por nombre

Hecho: hábitos, objetivos, eventos y recordatorios se pueden seleccionar por
UUID o por nombre/título exacto, sin distinguir mayúsculas ni tildes. Las
búsquedas se limitan al usuario y devuelven candidatos si no hay una única
coincidencia. También se pueden listar hábitos y recordatorios.

## Reglas del agente

Hecho: el agente delega en herramientas para crear eventos y recordatorios,
registrar o consultar hábitos, actualizar objetivos y listar el día. Si falta
una fecha, una hora queda sin franja, la duración de un evento o un nombre no
es único, pregunta antes de ejecutar la operación.

## Validación posterior y contexto

Hecho: el agente descarta respuestas fuera del catálogo, considera baja una
confianza ausente o ilegible y pasa al motor los últimos cuatro turnos junto
con la pregunta pendiente, si la hay.

## Puntos a revisar (por confirmar si son fallos)
1. `de_usuario` exige `usuario_id`; `Mensaje` y `RegistroHabito` no lo tienen.
2. RESUELTO: `hay_conflicto` solo compara eventos del mismo usuario.
3. `total_del_dia` y `racha_diaria` usan `valor` y `cumple`; el campo `completado` de `RegistroHabito` no interviene.
4. Los esquemas rechazan fechas sin zona; el dominio sigue aceptándolas si se crea el objeto a mano.
5. `Evento` solo valida al crearse; si se cambian las fechas después, no se revalida.
6. `racha_diaria` empieza en hoy o, si hoy aún no cumple, en ayer.
7. `actualizar_progreso` completa solo con 100 exacto.
8. `resumen_del_dia` solo considera hábitos de frecuencia diaria.
9. `historial_para_modelo` recorta con `limite` después de quitar mensajes vacíos.
