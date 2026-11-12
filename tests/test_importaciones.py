"""Hace cumplir las fronteras de importación entre las capas de ``app/``.

Analiza el código con ``ast`` sin importarlo, así que no ejecuta nada del
proyecto. Cada capa solo puede importar lo que indica ``REGLAS``; las capas
sin dependencias externas (``domain``, ``database``, ``repositories`` y
``services``) solo admiten la biblioteca estándar. ``sqlite3`` queda reservado
a ``database`` y ``repositories``, salvo la traducción de errores en ``tools``
y ``chatbot``; esas capas no ejecutan SQL.

Para permitir una dependencia nueva, amplía ``REGLAS`` aquí y deja constancia
en ``docs/arquitectura.md``.
"""

import ast
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent / "app"

# Prefijos de ``app`` que cada capa puede importar (ella misma incluida).
REGLAS = {
    "domain": ("app.domain",),
    "schemas": ("app.domain", "app.schemas"),
    "database": ("app.database",),
    "repositories": ("app.domain", "app.database", "app.repositories"),
    "services": (
        "app.domain",
        "app.schemas",
        "app.repositories.interfaces",
        "app.services",
    ),
    "tools": ("app.domain", "app.schemas", "app.services", "app.tools"),
    "llm": ("app.llm",),
    "agents": (
        "app.domain.message",
        "app.domain.lenguaje_fechas",
        "app.llm",
        "app.tools",
        "app.agents",
    ),
    "chatbot": (
        "app.composicion",
        "app.database",
        "app.domain.message",
        "app.llm.configuracion",
        "app.llm.ollama",
    ),
}

CAPAS_CON_TERCEROS = {"schemas", "tools", "llm", "agents"}
CAPAS_CON_SQLITE3 = {"database", "repositories", "tools", "chatbot"}
ARCHIVOS_EXENTOS = {"composicion.py"}
ARCHIVOS_LIBRES = {"__init__.py"}
PREFIJO_SQLITE = "app.repositories.sqlite_"


def _coincide(modulo, prefijo):
    return modulo == prefijo or modulo.startswith(prefijo + ".")


def _permitido(modulo, permitidos):
    return any(_coincide(modulo, prefijo) for prefijo in permitidos)


def _importaciones(arbol):
    """Devuelve ``(línea, módulo, hijos)``; ``módulo`` es None si es relativa."""
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                yield nodo.lineno, alias.name, []
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                yield nodo.lineno, None, []
            else:
                base = nodo.module or ""
                yield nodo.lineno, base, [f"{base}.{alias.name}" for alias in nodo.names]


def analizar(texto, capa, nombre="<código>"):
    """Devuelve las violaciones de las reglas de importación de un módulo."""
    permitidos = REGLAS.get(capa)
    violaciones = []
    for linea, modulo, hijos in sorted(_importaciones(ast.parse(texto)), key=lambda x: x[0]):
        donde = f"{nombre}:{linea}"
        if modulo is None:
            violaciones.append(f"{donde}: import relativo; usa rutas absolutas 'app.…'")
            continue
        candidatos = [modulo, *hijos]
        raiz_modulo = modulo.split(".")[0]
        if any(c.startswith(PREFIJO_SQLITE) for c in candidatos):
            violaciones.append(
                f"{donde}: {capa} importa {modulo}; "
                "las implementaciones sqlite_* solo las importa composicion.py"
            )
        elif modulo == "app" or modulo.startswith("app."):
            if permitidos is None:
                violaciones.append(f"{donde}: la capa '{capa}' no tiene regla en REGLAS")
            elif not (
                _permitido(modulo, permitidos)
                or (hijos and all(_permitido(h, permitidos) for h in hijos))
            ):
                violaciones.append(f"{donde}: {capa} no puede importar {modulo}")
        elif raiz_modulo == "sqlite3":
            if capa not in CAPAS_CON_SQLITE3:
                violaciones.append(f"{donde}: {capa} no puede usar sqlite3 directamente")
        elif raiz_modulo not in sys.stdlib_module_names:
            if capa not in CAPAS_CON_TERCEROS:
                violaciones.append(
                    f"{donde}: {capa} usa la biblioteca externa {raiz_modulo}; "
                    "esta capa solo admite la biblioteca estándar"
                )
    return violaciones


def violaciones_del_proyecto(raiz=RAIZ):
    """Analiza todos los archivos de ``raiz`` y junta las violaciones."""
    resultado = []
    for archivo in sorted(raiz.rglob("*.py")):
        relativo = archivo.relative_to(raiz)
        nombre = f"app/{relativo.as_posix()}"
        if len(relativo.parts) == 1:
            if relativo.name == "chatbot.py":
                texto = archivo.read_text(encoding="utf-8")
                resultado.extend(analizar(texto, "chatbot", nombre))
                continue
            if relativo.name in ARCHIVOS_EXENTOS | ARCHIVOS_LIBRES:
                continue
            resultado.append(f"{nombre}: archivo suelto en app/ sin regla")
            continue
        texto = archivo.read_text(encoding="utf-8")
        resultado.extend(analizar(texto, relativo.parts[0], nombre))
    return resultado


def test_el_codigo_del_proyecto_cumple_las_fronteras():
    violaciones = violaciones_del_proyecto()
    assert violaciones == [], "\n" + "\n".join(violaciones)


PROHIBIDOS = [
    ("domain", "from app.services.agenda import ServicioAgenda\n"),
    ("domain", "import pydantic\n"),
    ("schemas", "from app.repositories.interfaces import RepositorioUsuarios\n"),
    ("database", "from app.domain.user import Usuario\n"),
    ("repositories", "from app.services.errores import ErrorDeServicio\n"),
    ("repositories", "from app.repositories.sqlite_usuarios import RepositorioUsuariosSQLite\n"),
    ("services", "from app.repositories.sqlite_usuarios import RepositorioUsuariosSQLite\n"),
    ("services", "from app.repositories import sqlite_usuarios\n"),
    ("services", "import sqlite3\n"),
    ("services", "import httpx\n"),
    ("tools", "from app.repositories.interfaces import RepositorioEventos\n"),
    ("llm", "from app.domain.user import Usuario\n"),
    ("agents", "from app.services.agenda import ServicioAgenda\n"),
    ("agents", "from app.repositories.interfaces import RepositorioEventos\n"),
    ("agents", "import sqlite3\n"),
    ("chatbot", "from app.services.agenda import ServicioAgenda\n"),
    ("chatbot", "from app.repositories.interfaces import RepositorioEventos\n"),
    ("chatbot", "from app.domain.nba.fuente import FuenteNBA\n"),
    ("domain", "from .user import Usuario\n"),
    ("capa_inventada", "from app.domain.user import Usuario\n"),
]

PERMITIDOS = [
    ("domain", "from __future__ import annotations\nfrom dataclasses import dataclass\n"
               "from app.domain.user import Usuario\n"),
    ("schemas", "from pydantic import BaseModel\nfrom app.domain.user import Usuario\n"),
    ("repositories", "import sqlite3\nfrom app.database.fechas import a_texto\n"
                     "from app.domain.user import Usuario\n"
                     "from app.repositories.interfaces import RepositorioUsuarios\n"),
    ("services", "from app.repositories import interfaces\n"
                 "from app.repositories.interfaces import RepositorioEventos\n"
                 "from app.schemas.user import UsuarioSchema\n"),
    ("agents", "from app.domain.message import Mensaje\n"
               "from app.domain.lenguaje_fechas import resolver_fecha\n"
               "from app.llm.backend import LLMBackend\n"
               "from app.tools.base import Herramienta\n"),
    ("llm", "import json\nfrom pydantic import BaseModel\n"),
    ("database", "import sqlite3\nfrom app.database.fechas import a_texto\n"),
    ("tools", "import sqlite3\nfrom app.services.errores import ErrorDeServicio\n"),
    (
        "chatbot",
        "import sqlite3\nfrom app.database.connection import sesion_sqlite\n",
    ),
    ("chatbot", "from app.composicion import crear_composicion\n"
                "from app.llm.ollama import MotorOllama\n"),
    ("chatbot", "from app.domain.message import RolMensaje\n"
                "from app.database.connection import sesion_sqlite\n"),
]


@pytest.mark.parametrize("capa,codigo", PROHIBIDOS)
def test_detecta_las_importaciones_prohibidas(capa, codigo):
    assert analizar(codigo, capa), f"{capa} debería rechazar: {codigo!r}"


@pytest.mark.parametrize("capa,codigo", PERMITIDOS)
def test_acepta_las_importaciones_permitidas(capa, codigo):
    assert analizar(codigo, capa) == []


def test_el_mensaje_indica_archivo_y_linea(tmp_path):
    (tmp_path / "domain").mkdir()
    (tmp_path / "domain" / "malo.py").write_text(
        "from uuid import UUID\nfrom app.services.agenda import ServicioAgenda\n",
        encoding="utf-8",
    )
    violaciones = violaciones_del_proyecto(tmp_path)
    assert len(violaciones) == 1
    assert violaciones[0].startswith("app/domain/malo.py:2:")


def test_composicion_puede_importar_las_implementaciones_sqlite(tmp_path):
    (tmp_path / "composicion.py").write_text(
        "from app.repositories.sqlite_usuarios import RepositorioUsuariosSQLite\n",
        encoding="utf-8",
    )
    assert violaciones_del_proyecto(tmp_path) == []


def test_un_archivo_suelto_en_app_necesita_regla(tmp_path):
    (tmp_path / "utilidades.py").write_text("X = 1\n", encoding="utf-8")
    assert violaciones_del_proyecto(tmp_path) == ["app/utilidades.py: archivo suelto en app/ sin regla"]
