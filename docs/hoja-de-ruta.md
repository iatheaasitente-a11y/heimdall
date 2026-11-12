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
8. Agentes concretos (personal, NBA) — pendiente
9. Fábrica y router — pendiente
10. Chatbot (herramientas, interfaz) — pendiente

Fuera de alcance por ahora: FastAPI, Telegram, predicciones NBA, modelo de IA.

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
