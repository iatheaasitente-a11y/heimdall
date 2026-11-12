# heimdall — documentación

Chatbot-agente en Python con dos áreas: asistente personal (horarios, hábitos,
objetivos, recordatorios) y módulo NBA. Principio central: el modelo de
lenguaje interpreta y explica; Python calcula; SQLite conserva los datos.

## Índice
| Documento | Contenido |
|---|---|
| [arquitectura.md](arquitectura.md) | Capas, flujo de una petición, reglas |
| [dominio.md](dominio.md) | Clases, campos y métodos |
| [decisiones.md](decisiones.md) | Decisiones de diseño y motivos |
| [base-de-datos.md](base-de-datos.md) | Tablas SQLite y formatos |
| [servicios.md](servicios.md) | Casos de uso y errores |
| [auditoria-duplicacion-2026-11-12.md](auditoria-duplicacion-2026-11-12.md) | Auditoría y refactor de duplicación |
| [pruebas.md](pruebas.md) | Tests y convenciones |
| [hoja-de-ruta.md](hoja-de-ruta.md) | Qué falta y qué revisar |

## Estado (12 nov 2026)
- Dominio y relaciones: hecho.
- Esquemas Pydantic: hechos para todas las clases.
- Base de datos SQLite (esquema y conexión): hecha.
- Repositorios SQLite: hechos para todas las entidades.
- Los seis servicios, herramientas, agentes y chatbot de terminal están implementados.
- Telegram dispone de conector con transporte falso; el arranque y el origen del mapeo de identidad siguen pendientes.
- `app/domain/nba/` está vacío a propósito.
- Última suite completa: 772 tests aprobados y 2 omitidos.

## Ejecutar
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
Requiere Python 3.11 o superior (`StrEnum`, `datetime.UTC`). Probado con 3.14.
