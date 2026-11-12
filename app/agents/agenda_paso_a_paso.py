"""Agendado paso a paso para crear eventos preguntando los datos que faltan."""

import re
import unicodedata
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from uuid import UUID

CAMPOS = ("titulo", "dia", "hora", "duracion")

PREGUNTAS = {
    "titulo": "¿Cómo se llama el evento?",
    "dia": "¿Para qué día lo quieres?",
    "hora": "¿A qué hora?",
    "duracion": "¿Cuánto durará?",
}

FRASES_INICIO = (
    "crea un evento",
    "crear un evento",
    "agenda",
    "agendar",
    "quiero agendar",
    "ponme una cita",
)

FRASES_CANCELAR = ("cancela", "cancelar", "cancela eso", "olvidalo")


class AgendaPasoAPaso:
    """Conversación guiada para crear un evento cuando faltan datos."""

    def __init__(
        self,
        crear_evento: Callable[[UUID, dict[str, str]], dict[str, object]],
        resolver_fecha: Callable[[str], object] | None = None,
    ) -> None:
        """Guarda la función de creación y el resolutor opcional de fechas."""
        self._crear_evento = crear_evento
        self._resolver_fecha = resolver_fecha
        self._borradores: dict[tuple[UUID, UUID], dict[str, str]] = defaultdict(dict)

    def procesar(
        self,
        usuario_id: UUID,
        conversacion_id: UUID,
        texto: str,
        historial: Sequence[Mapping[str, str]] | None = None,
    ) -> dict[str, object] | None:
        """Devuelve una pregunta, un error o el resultado de crear el evento."""
        clave = (usuario_id, conversacion_id)
        if clave not in self._borradores and not self._es_inicio(texto):
            return None
        borrador = self._borradores[clave]
        if self._es_cancelacion(texto):
            self._borradores.pop(clave, None)
            return {"ok": True, "datos": {"mensaje": "Agendado cancelado."}}
        if not borrador and not self._es_inicio(texto):
            return None
        self._extraer(texto, borrador)
        pendientes = [campo for campo in CAMPOS if campo not in borrador]
        if pendientes:
            return {"ok": True, "datos": {"pregunta": PREGUNTAS[pendientes[0]]}}
        datos = {campo: borrador[campo] for campo in CAMPOS}
        self._borradores.pop(clave, None)
        return self._crear_evento(usuario_id, datos)

    def _es_inicio(self, texto: str) -> bool:
        """Reconoce frases que inician un agendado."""
        normalizado = self._normalizar(texto)
        return any(frase in normalizado for frase in FRASES_INICIO)

    def _es_cancelacion(self, texto: str) -> bool:
        """Reconoce frases que cancelan el agendado en curso."""
        normalizado = self._normalizar(texto)
        return normalizado in FRASES_CANCELAR

    def _extraer(self, texto: str, borrador: dict[str, str]) -> None:
        """Añade al borrador los campos reconocibles del mensaje."""
        if "titulo" not in borrador:
            titulo = self._extraer_titulo(texto)
            if titulo:
                borrador["titulo"] = titulo
        if "dia" not in borrador:
            dia = self._extraer_dia(texto)
            if dia:
                borrador["dia"] = dia
        if "hora" not in borrador:
            hora = self._extraer_hora(texto)
            if hora:
                borrador["hora"] = hora
        if "duracion" not in borrador:
            duracion = self._extraer_duracion(texto)
            if duracion:
                borrador["duracion"] = duracion

    def _extraer_titulo(self, texto: str) -> str | None:
        """Extrae el título tras 'evento', 'cita' o 'reunión'."""
        patron = r"(?:crea(?:r)?\s+un\s+evento|agendar|agenda|cita|reuni[oó]n)\s+(?:de\s+|sobre\s+)?(.+)"
        coincidencia = re.search(patron, texto, re.IGNORECASE)
        if coincidencia:
            return coincidencia.group(1).strip(" .")
        return None

    def _extraer_dia(self, texto: str) -> str | None:
        """Devuelve el día reconocido o delega en el resolutor inyectado."""
        patron = r"\b(hoy|mañana|pasado mañana)\b"
        coincidencia = re.search(patron, texto, re.IGNORECASE)
        if coincidencia:
            return coincidencia.group(1).lower()
        return None

    def _extraer_hora(self, texto: str) -> str | None:
        """Extrae una hora en formato 'a las 10' o 'a las 10:30'."""
        patron = r"\ba las?\s+(\d{1,2})(?::(\d{2}))?"
        coincidencia = re.search(patron, texto, re.IGNORECASE)
        if not coincidencia:
            return None
        hora = coincidencia.group(1)
        minutos = coincidencia.group(2) or "00"
        return f"{hora}:{minutos}"

    def _extraer_duracion(self, texto: str) -> str | None:
        """Extrae una duración en minutos u horas."""
        patron = r"(\d+)\s*(minuto|min|minutos|hora|horas|h)\b"
        coincidencia = re.search(patron, texto, re.IGNORECASE)
        if not coincidencia:
            return None
        cantidad = coincidencia.group(1)
        unidad = coincidencia.group(2).lower()
        if unidad.startswith("h"):
            return f"{cantidad} horas"
        return f"{cantidad} minutos"

    def _normalizar(self, texto: str) -> str:
        """Pasa el texto a minúsculas sin tildes ni puntuación final."""
        sin_tildes = unicodedata.normalize("NFKD", texto.casefold())
        caracteres = [c for c in sin_tildes if not unicodedata.combining(c)]
        return "".join(caracteres).strip(" .!?,")
