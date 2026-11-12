# Decisiones de diseño

| # | Decisión | Motivo |
|---|---|---|
| 1 | Enlazar objetos por `*_id` | Encaja con tablas SQL y evita ciclos |
| 2 | Fechas con zona, guardadas en UTC | Evita errores de cambio de hora; se convierte solo para mostrar |
| 3 | Celdas de horario calculadas, no guardadas | Una sola fuente de verdad: los eventos |
| 4 | Validar en `__post_init__` | Un objeto inválido no llega a existir |
| 5 | `relations.py` con funciones puras | Fáciles de probar y sin estado |
| 6 | Estados (cancelado, completado) en vez de borrar | Conserva historial |
| 7 | `StrEnum` para estados y roles | Se serializan como texto legible |
| 8 | El modelo de lenguaje no toca la base de datos | Seguridad y control; solo usa herramientas |
| 9 | `resumen_del_dia` sin modelo de lenguaje | Respuesta rápida, exacta y comprobable |
| 10 | Medir con un CSV de frases antes de añadir canales | Lección de femix: no crecer antes de medir |
| 11 | Estados con transiciones estrictas | Un objeto cerrado no se reabre por accidente; la corrección manual es explícita (`restablecer()`) |
| 12 | Conservar objetivos cerrados | Historial consultable; `restablecer()` es explícito |
| 13 | Cerrar conversaciones y conservar sus mensajes | No se borran ni se editan los mensajes; el historial queda disponible |
