"""Reglas deterministas para las solicitudes personales frecuentes."""

import re
import unicodedata
from collections.abc import Callable
from datetime import date, datetime, timedelta
from uuid import UUID

from app.domain.lenguaje_fechas import (
    FechaHoraResuelta,
    HoraResuelta,
    resolver_fecha,
    resolver_fecha_hora,
    resolver_hora,
)
from app.tools.registro import RegistroHerramientas

_NUMERO = r"\d+(?:[.,]\d+)?|una?|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce"
_PALABRAS_NUMERO = {
    "un": 1,
    "una": 1,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "once": 11,
    "doce": 12,
}
_VERBOS_PROGRESO = (
    "bebido",
    "caminado",
    "comido",
    "corrid[oa]",
    "estudiado",
    "hecho",
    "le[ií]do",
    "practicado",
    "tomado",
    "entrenado",
)
_PATRON_PROGRESO = re.compile(
    rf"\b(?:he\s+)?(?:{'|'.join(_VERBOS_PROGRESO)})\s+(?P<resto>.+)$"
)
_PATRON_CANTIDAD = re.compile(
    rf"^\s*(?P<valor>{_NUMERO})"
    r"(?:\s+(?:litros?|mililitros?|km|kil[oó]metros?|"
    r"horas?|minutos?|vasos?|tazas?|gramos?|p[aá]ginas?|veces))?"
    r"(?:\s+de)?\s+(?P<nombre>.+)$"
)
_PATRON_HORA_TEXTO = re.compile(
    rf"\b(?:a\s+las|a\s+la|las)\s+(?:{_NUMERO})"
    r"(?:\s+y\s+(?:media|cuarto)|\s+menos\s+cuarto)?"
    r"(?:\s*(?:am|pm))?\b",
    re.IGNORECASE,
)
_PATRON_FECHA_TEXTO = re.compile(
    r"\b(?:pasado\s+mañana|pasado\s+manana|mañana|manana|hoy|"
    r"anteayer|ayer|(?:el\s+)?lunes|(?:el\s+)?martes|"
    r"(?:el\s+)?mi[eé]rcoles|(?:el\s+)?jueves|(?:el\s+)?viernes|"
    r"(?:el\s+)?s[aá]bado|(?:el\s+)?domingo|"
    r"esta\s+(?:mañana|manana|tarde|noche)|"
    r"el\s+\d{1,2}(?:\s+de)?\s+"
    r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|setiembre|octubre|noviembre|diciembre)|"
    r"\d{4}-\d{1,2}-\d{1,2})\b",
    re.IGNORECASE,
)
_PATRON_FRANJA_TEXTO = re.compile(
    r"\b(?:(?:de|por) la|esta)\s+"
    r"(?:mañana|manana|tarde|noche|madrugada)\b",
    re.IGNORECASE,
)
_PATRON_DURACION = re.compile(
    rf"\b(?:durante\s+)?(?P<cantidad>{_NUMERO})\s+"
    r"(?P<unidad>horas?|minutos?)\b",
    re.IGNORECASE,
)
_PATRON_EVENTO = re.compile(
    r"\b(?:evento|cita|reuni[oó]n)\b|"
    r"\b(?:agendar|agenda|apuntar|apunta|anotar|anota|crear|crea)\s+"
    r"(?:un\s+)?(?:evento|cita|reuni[oó]n)\b"
)
_PATRON_RECORDATORIO = re.compile(
    r"\brecu[eé]rdame\b|"
    r"\b(?:programa|programar|crea|crear)\s+(?:un\s+)?recordatorio\b"
)


class ReglasDeterministas:
    """Interpreta patrones frecuentes y delega su ejecución en herramientas."""

    def __init__(
        self,
        herramientas: RegistroHerramientas,
        hoy_por_usuario: Callable[[UUID], date],
        ahora_por_usuario: Callable[[UUID], datetime] | None,
    ) -> None:
        """Asocia las herramientas y el reloj local inyectado por usuario."""
        self._herramientas = herramientas
        self._hoy_por_usuario = hoy_por_usuario
        self._ahora_por_usuario = ahora_por_usuario
        self._eventos_pendientes: dict[UUID, dict[str, object]] = {}
        self._acciones_pendientes: dict[UUID, dict[str, object]] = {}

    def procesar(self, usuario_id: UUID, texto: str) -> dict[str, object] | None:
        """Resuelve una solicitud reconocida o devuelve ``None`` si no hay regla."""
        normalizado = _normalizar(texto)

        pendiente = self._eventos_pendientes.get(usuario_id)
        if pendiente is not None:
            if normalizado in {"si", "vale", "confirmo", "confirmar"}:
                self._eventos_pendientes.pop(usuario_id)
                resultado = self._herramientas.obtener(
                    "agenda_crear_evento"
                ).ejecutar(usuario_id, pendiente)
                if resultado.get("ok") is True and isinstance(
                    resultado.get("datos"), dict
                ):
                    ahora = self._ahora(usuario_id)
                    zona = ahora.tzinfo if ahora is not None else None
                    texto = _texto_evento_creado(resultado["datos"], zona)
                    if texto is not None:
                        return {"ok": True, "datos": texto}
                return resultado
            if normalizado in {"no", "cancela", "cancelar"}:
                self._eventos_pendientes.pop(usuario_id)
                return {
                    "ok": True,
                    "datos": "He cancelado la creacion del evento.",
                }

        respuesta_conversacion = _respuesta_conversacion(normalizado)
        if respuesta_conversacion is not None:
            return respuesta_conversacion
        rango = _rango_de_periodo(normalizado, self._hoy(usuario_id))
        if rango is not None:
            return self._consultar_periodo(usuario_id, rango)

        if _es_resumen_de_hoy(normalizado):
            return self._herramientas.obtener("resumen_del_dia").ejecutar(
                usuario_id,
                {"dia": self._hoy(usuario_id)},
            )
        accion_pendiente = self._acciones_pendientes.get(usuario_id)
        if accion_pendiente is not None:
            if normalizado in {"si", "vale", "confirmo", "confirmar"}:
                self._acciones_pendientes.pop(usuario_id)
                return self._herramientas.obtener(
                    accion_pendiente["herramienta"]
                ).ejecutar(usuario_id, accion_pendiente["argumentos"])
            if normalizado in {"no", "cancela", "cancelar"}:
                self._acciones_pendientes.pop(usuario_id)
                return {
                    "ok": True,
                    "datos": "He cancelado la operacion.",
                }

        accion = _detectar_accion(normalizado)
        if accion is not None:
            self._acciones_pendientes[usuario_id] = accion
            return {"ok": True, "datos": accion["propuesta"]}

        if _PATRON_RECORDATORIO.search(normalizado):
            return self._crear_recordatorio(usuario_id, texto)
        if _PATRON_EVENTO.search(normalizado):
            return self._crear_evento(usuario_id, texto)
        if _PATRON_PROGRESO.search(normalizado):
            return self._registrar_progreso(usuario_id, texto, normalizado)
        if _es_actualizacion_objetivo(normalizado):
            return self._actualizar_objetivo(usuario_id, normalizado)
        if _es_consulta_habito(normalizado):
            return self._consultar_habito(usuario_id, normalizado)
        return None

    def _consultar_periodo(
        self,
        usuario_id: UUID,
        rango: tuple[date, date, str],
    ) -> dict[str, object]:
        """Lista los eventos activos dentro de un rango de fechas."""

        inicio, fin, etiqueta = rango
        eventos = []
        dia = inicio

        while dia <= fin:
            resultado = self._herramientas.obtener(
                "agenda_eventos_del_dia"
            ).ejecutar(usuario_id, {"dia": dia})
            if resultado.get("ok") is True:
                eventos.extend(resultado.get("datos") or [])
            dia += timedelta(days=1)

        if not eventos:
            return {
                "ok": True,
                "datos": f"No tienes eventos {etiqueta}.",
            }

        ahora = self._ahora(usuario_id)
        zona = ahora.tzinfo if ahora is not None else None
        cantidad = (
            "un evento"
            if len(eventos) == 1
            else f"{len(eventos)} eventos"
        )
        lineas = [f"Tienes {cantidad} {etiqueta}:"]

        for evento in eventos:
            texto = _texto_evento(evento, zona)
            if texto is not None:
                lineas.append(texto)

        return {"ok": True, "datos": "\n".join(lineas)}

    def _crear_evento(self, usuario_id: UUID, texto: str) -> dict[str, object]:
        """Crea un evento solo cuando la fecha, hora, título y duración son claros."""
        ahora = self._ahora(usuario_id)
        if ahora is None:
            return _preguntar("¿Qué día y a qué hora quieres el evento?")
        resuelta = self._resolver_fecha_hora(texto, ahora)
        if isinstance(resuelta, dict):
            return resuelta
        fecha_hora = resuelta
        if fecha_hora.hora is None:
            return _preguntar("¿A qué hora quieres que empiece el evento?")
        titulo = _titulo_evento(texto)
        if not titulo:
            return _preguntar("¿Qué título quieres ponerle al evento?")
        duracion = _duracion_explicita(texto)
        if duracion is None:
            return _preguntar("¿Cuánto dura el evento o a qué hora termina?")
        comienza = datetime.combine(
            fecha_hora.fecha,
            fecha_hora.hora,
            tzinfo=ahora.tzinfo,
        )
        termina = comienza + duracion
        try:
            herramienta_dia = self._herramientas.obtener(
                "agenda_eventos_del_dia"
            )
        except KeyError:
            herramienta_dia = None

        existentes = (
            herramienta_dia.ejecutar(usuario_id, {"dia": comienza.date()})
            if herramienta_dia is not None
            else {"ok": False}
        )

        mismo_nombre = False

        if existentes.get("ok") is True:
            for evento in existentes.get("datos") or []:
                if not isinstance(evento, dict):
                    continue

                inicio = _a_zona(evento.get("comienza"), ahora.tzinfo)
                fin = _a_zona(evento.get("termina"), ahora.tzinfo)

                if inicio is None or fin is None:
                    continue

                if comienza < fin and termina > inicio:
                    return {
                        "ok": False,
                        "error": (
                            f"Ya tienes '{evento.get('titulo', 'un evento')}' "
                            f"de {inicio.strftime('%H:%M')} a "
                            f"{fin.strftime('%H:%M')} ese dia. "
                            "Elige otro horario o cancela el evento existente."
                        ),
                    }

                if (
                    str(evento.get("titulo", "")).strip().lower()
                    == titulo.lower()
                ):
                    mismo_nombre = True

        argumentos = {
            "titulo": titulo,
            "comienza": comienza,
            "termina": termina,
        }
        self._eventos_pendientes[usuario_id] = argumentos

        if duracion.total_seconds() % 3600 == 0:
            duracion_texto = f"{int(duracion.total_seconds() // 3600)} hora(s)"
        else:
            duracion_texto = f"{int(duracion.total_seconds() // 60)} minutos"

        aviso = ""
        if mismo_nombre:
            aviso = "\n\nYa tienes un evento con ese nombre ese dia."

        propuesta = (
            "Voy a crear este evento:\n"
            f"\u2022 {titulo}\n"
            f"\u2022 {comienza.strftime('%d/%m/%Y %H:%M')}\n"
            f"\u2022 Duracion: {duracion_texto}"
            f"{aviso}\n\n"
            "Responde si para confirmar o no para cancelar."
        )
        return {"ok": True, "datos": propuesta}

    def _crear_recordatorio(self, usuario_id: UUID, texto: str) -> dict[str, object]:
        """Programa un recordatorio cuando su mensaje y momento están explícitos."""
        ahora = self._ahora(usuario_id)
        if ahora is None:
            return _preguntar("¿Qué día y a qué hora quieres el recordatorio?")
        resuelta = self._resolver_fecha_hora(texto, ahora)
        if isinstance(resuelta, dict):
            return resuelta
        if resuelta.hora is None:
            return _preguntar("¿A qué hora quieres el recordatorio?")
        mensaje = _mensaje_recordatorio(texto)
        if not mensaje:
            return _preguntar("¿Qué quieres que te recuerde?")
        cuando = datetime.combine(
            resuelta.fecha,
            resuelta.hora,
            tzinfo=ahora.tzinfo,
        )
        return self._herramientas.obtener("recordatorios_programar").ejecutar(
            usuario_id,
            {"mensaje": mensaje, "cuando": cuando},
        )

    def _registrar_progreso(
        self,
        usuario_id: UUID,
        texto: str,
        normalizado: str,
    ) -> dict[str, object]:
        """Registra una cantidad dicha para un hábito y una fecha expresos."""
        coincidencia = _PATRON_PROGRESO.search(normalizado)
        if coincidencia is None:
            return _preguntar("¿Qué cantidad de progreso quieres registrar?")
        cantidad = _PATRON_CANTIDAD.match(coincidencia.group("resto"))
        if cantidad is None:
            return _preguntar("¿Qué cantidad de progreso quieres registrar?")
        nombre = _limpiar_tiempos(cantidad.group("nombre"))
        if not nombre:
            return _preguntar("¿De qué hábito es ese progreso?")
        ahora = self._ahora(usuario_id)
        if ahora is None:
            return _preguntar("¿De qué día es ese progreso?")
        dia = resolver_fecha(texto, ahora, permitir_pasado=True)
        if dia is None:
            return _preguntar("¿De qué día es ese progreso? Puedes decir hoy, ayer o anteayer.")
        seleccion = self._seleccionar_nombre(
            usuario_id,
            nombre,
            "habitos_listar",
            "nombre",
            "hábito",
            exacto=True,
        )
        if isinstance(seleccion, dict):
            return seleccion
        cuando = ahora.replace(year=dia.year, month=dia.month, day=dia.day)
        return self._herramientas.obtener("habitos_registrar_progreso").ejecutar(
            usuario_id,
            {
                "nombre": seleccion,
                "valor": _numero(cantidad.group("valor")),
                "cuando": cuando,
            },
        )

    def _consultar_habito(
        self,
        usuario_id: UUID,
        texto: str,
    ) -> dict[str, object]:
        """Consulta progreso o racha para un hábito y día identificables."""
        ahora = self._ahora(usuario_id)
        if ahora is None:
            return _preguntar("¿Para qué día quieres consultar el hábito?")
        dia = resolver_fecha(texto, ahora, permitir_pasado=True)
        if dia is None:
            return _preguntar("¿Para qué día quieres consultar el hábito?")
        nombre = self._seleccionar_nombre(
            usuario_id,
            texto,
            "habitos_listar",
            "nombre",
            "hábito",
        )
        if isinstance(nombre, dict):
            return nombre
        herramienta = (
            "habitos_racha" if "racha" in texto else "habitos_progreso_del_dia"
        )
        return self._herramientas.obtener(herramienta).ejecutar(
            usuario_id,
            {"nombre": nombre, "dia": dia},
        )

    def _actualizar_objetivo(
        self,
        usuario_id: UUID,
        texto: str,
    ) -> dict[str, object]:
        """Actualiza el porcentaje explícito de un objetivo por su nombre."""
        progreso = re.search(r"\b(\d+(?:[.,]\d+)?)\s*%", texto)
        if progreso is None:
            return _preguntar("¿A qué porcentaje quieres actualizar el objetivo?")
        nombre = self._seleccionar_nombre(
            usuario_id,
            texto,
            "objetivos_listar",
            "nombre",
            "objetivo",
        )
        if isinstance(nombre, dict):
            return nombre
        return self._herramientas.obtener(
            "objetivos_actualizar_progreso"
        ).ejecutar(
            usuario_id,
            {
                "nombre": nombre,
                "progreso": float(progreso.group(1).replace(",", ".")),
            },
        )

    def _resolver_fecha_hora(
        self,
        texto: str,
        ahora: datetime,
    ) -> FechaHoraResuelta | dict[str, object]:
        """Pide aclaración ante fecha, hora o franja no resueltas."""
        if resolver_fecha(texto, ahora) is None:
            return _preguntar("¿Qué día quieres? Indica una fecha que pueda resolver.")
        hora = resolver_hora(texto)
        if hora is None:
            return _preguntar("¿A qué hora quieres que ocurra?")
        if not hora.acotada:
            if hora.hora.hour < 12:
                hora = HoraResuelta(hora.hora, True, "mañana")
            else:
                return _preguntar(
                    "¿Te refieres a la tarde o a la noche?"
                )
        resuelta = resolver_fecha_hora(texto, ahora)
        if resuelta is None or resuelta.hora is None:
            return _preguntar("¿Qué fecha y hora futura quieres indicar?")
        return resuelta

    def _seleccionar_nombre(
        self,
        usuario_id: UUID,
        texto: str,
        herramienta_lista: str,
        campo_nombre: str,
        tipo: str,
        exacto: bool = False,
    ) -> str | dict[str, object]:
        """Busca nombres entre los elementos listados por una herramienta."""
        lista = self._herramientas.obtener(herramienta_lista).ejecutar(
            usuario_id,
            {},
        )
        if not lista["ok"]:
            return lista
        elementos = lista["datos"]
        if not isinstance(elementos, list):
            raise TypeError("La herramienta de listado debe devolver una lista.")
        referencia = _normalizar(texto)
        coincidencias = [
            elemento
            for elemento in elementos
            if isinstance(elemento, dict)
            and isinstance(elemento.get(campo_nombre), str)
            and (
                _normalizar(elemento[campo_nombre]) == referencia
                if exacto
                else _contiene_nombre(referencia, _normalizar(elemento[campo_nombre]))
            )
        ]
        if not coincidencias:
            return _preguntar(f"¿Cuál es el nombre exacto del {tipo}?")
        if len(coincidencias) > 1:
            return {
                "ok": False,
                "error": f"He encontrado más de un {tipo}. ¿Cuál quieres decir?",
                "candidatos": [
                    {"id": item.get("id"), "nombre": item.get(campo_nombre)}
                    for item in coincidencias
                ],
            }
        return coincidencias[0][campo_nombre]

    def _hoy(self, usuario_id: UUID) -> date:
        """Devuelve el día local a partir del instante inyectado."""
        ahora = self._ahora(usuario_id)
        return ahora.date() if ahora is not None else self._hoy_por_usuario(usuario_id)

    def _ahora(self, usuario_id: UUID) -> datetime | None:
        """Devuelve la hora local del usuario, o ``None`` si no se inyectó."""
        if self._ahora_por_usuario is None:
            return None
        return self._ahora_por_usuario(usuario_id)


_PATRON_RESUMEN_HOY = re.compile(
    r"\b(?:"
    r"que\s+(?:tengo|hay|eventos?\s+tengo|eventos?\s+hay|citas?\s+tengo|"
    r"citas?\s+hay|recordatorios?\s+tengo|recordatorios?\s+hay)"
    r"|"
    r"(?:mis\s+)?(?:eventos?|citas?|agenda|recordatorios?)\s+"
    r"(?:de|para|del)\s+hoy"
    r"|"
    r"(?:lista|listar|muestrame|ensename)\s+"
    r"(?:lo\s+de\s+hoy|mi\s+agenda\s+de\s+hoy|mis\s+eventos\s+de\s+hoy)"
    r"|"
    r"resumen\s+(?:de\s+)?(?:hoy|el\s+dia)"
    r")\b",
    re.IGNORECASE,
)


_PATRON_RESUMEN_HOY = re.compile(
    r"\b(?:"
    r"que\s+(?:tengo|hay|eventos?\s+tengo|eventos?\s+hay|citas?\s+tengo|"
    r"citas?\s+hay|recordatorios?\s+tengo|recordatorios?\s+hay)"
    r"|"
    r"(?:mis\s+)?(?:eventos?|citas?|agenda|recordatorios?)\s+"
    r"(?:de|para|del)\s+hoy"
    r"|"
    r"(?:lista|listar|muestrame|ensename)\s+"
    r"(?:lo\s+de\s+hoy|mi\s+agenda\s+de\s+hoy|mis\s+eventos\s+de\s+hoy)"
    r"|"
    r"resumen\s+(?:de\s+)?(?:hoy|el\s+dia)"
    r")\b",
    re.IGNORECASE,
)


def _es_resumen_de_hoy(texto: str) -> bool:
    """Reconoce consultas breves sobre los elementos del dia actual."""
    return _PATRON_RESUMEN_HOY.search(texto) is not None

def _es_consulta_habito(texto: str) -> bool:
    """Reconoce preguntas de progreso o racha que mencionan un hábito."""
    return "racha" in texto or any(
        frase in texto
        for frase in ("cuanto llevo", "cuanto he", "progreso de", "progreso del")
    )


def _es_actualizacion_objetivo(texto: str) -> bool:
    """Reconoce peticiones de actualización aunque falte el porcentaje."""
    return "objetivo" in texto and any(
        palabra in texto
        for palabra in ("actualiza", "actualizar", "progreso", "llevo", "%")
    )


def _titulo_evento(texto: str) -> str:
    """Extrae el título eliminando fecha, hora y verbos de orden."""
    titulo = _limpiar_tiempos(texto)
    titulo = re.sub(
        r"\b(?:por favor|crea|crear|agenda|agendar|apunta|apuntar|"
        r"anota|anotar|añade|anadir|pon)\b",
        " ",
        titulo,
        flags=re.IGNORECASE,
    )
    titulo = re.sub(r"\bevento\b", " ", titulo, flags=re.IGNORECASE)
    titulo = re.sub(r"^\s*(?:un|una)\s+", " ", titulo, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", titulo).strip(" \t\n,.;:!?¿¡-")


def _mensaje_recordatorio(texto: str) -> str:
    """Extrae el contenido de un recordatorio antes de su fecha y hora."""
    mensaje = re.sub(
        r"^\s*(?:por favor\s+)?(?:recu[eé]rdame|"
        r"(?:(?:programa|programar|crea|crear)\s+)?"
        r"(?:un\s+)?recordatorio(?:\s+para)?)\s*",
        "",
        texto,
        flags=re.IGNORECASE,
    )
    return _limpiar_tiempos(mensaje).strip(" \t\n,.;:!?¿¡-")


def _limpiar_tiempos(texto: str) -> str:
    """Quita fragmentos temporales sin alterar el contenido restante."""
    texto = _PATRON_HORA_TEXTO.sub(" ", texto)
    texto = _PATRON_DURACION.sub(" ", texto)
    texto = _PATRON_FRANJA_TEXTO.sub(" ", texto)
    texto = _PATRON_FECHA_TEXTO.sub(" ", texto)
    return re.sub(r"\s+", " ", texto).strip(" \t\n,.;:!?¿¡-")


def _duracion_explicita(texto: str) -> timedelta | None:
    """Convierte una duración expresada en horas o minutos."""
    coincidencia = _PATRON_DURACION.search(_normalizar(texto))
    if coincidencia is None:
        return None
    cantidad = _numero(coincidencia.group("cantidad"))
    if coincidencia.group("unidad").startswith("hora"):
        return timedelta(hours=cantidad)
    return timedelta(minutes=cantidad)


def _numero(texto: str) -> float:
    """Interpreta cifras o números frecuentes escritos en palabras."""
    if texto in _PALABRAS_NUMERO:
        return float(_PALABRAS_NUMERO[texto])
    return float(texto.replace(",", "."))


def _contiene_nombre(texto: str, nombre: str) -> bool:
    """Comprueba que el nombre completo aparezca como una expresión separada."""
    return re.search(rf"(?<!\w){re.escape(nombre)}(?!\w)", texto) is not None


def _normalizar(texto: str) -> str:
    """Ignora mayúsculas, tildes, puntuación exterior y espacios repetidos."""
    descompuesto = unicodedata.normalize("NFKD", texto.casefold())
    sin_tildes = "".join(
        caracter
        for caracter in descompuesto
        if not unicodedata.combining(caracter)
    )
    return " ".join(sin_tildes.split()).strip(" \t\n,.;:!?¿¡-")


def _preguntar(mensaje: str) -> dict[str, object]:
    """Representa una aclaración necesaria sin ejecutar una herramienta."""
    return {"ok": False, "error": mensaje}


def _respuesta_conversacion(texto: str) -> dict[str, object] | None:
    """Responde mensajes sociales frecuentes sin consultar el LLM."""

    if re.search(
        r"\b(hola|buenas|buenos dias|buenas tardes|buenas noches|"
        r"que tal|como estas|como va)\b",
        texto,
    ):
        return {"ok": True, "datos": "¡Hola! ¿En qué te ayudo?"}

    if re.search(r"\b(quien eres|que eres)\b", texto):
        return {
            "ok": True,
            "datos": (
                "Soy Fenix, tu asistente personal. Puedo ayudarte con "
                "agenda, hábitos, objetivos y recordatorios."
            ),
        }

    if re.search(
        r"\b(que puedes hacer|que sabes hacer|ayuda|que haces)\b",
        texto,
    ):
        return {
            "ok": True,
            "datos": (
                "Puedo ayudarte con agenda, hábitos, objetivos y "
                "recordatorios."
            ),
        }

    if re.search(r"\bgracias\b", texto):
        return {"ok": True, "datos": "¡De nada!"}

    if re.search(r"\b(adios|hasta luego|chao)\b", texto):
        return {"ok": True, "datos": "¡Hasta luego!"}

    return None


def _rango_de_periodo(texto: str, hoy: date) -> tuple[date, date, str] | None:
    """Reconoce rangos frecuentes: semana, mes y fin de semana."""

    if re.search(r"\b(?:esta semana|semana actual)\b", texto, re.IGNORECASE):
        inicio = hoy - timedelta(days=hoy.weekday())
        return inicio, inicio + timedelta(days=6), "esta semana"

    if re.search(
        r"\b(?:proxima semana|la proxima semana|siguiente semana)\b",
        texto,
        re.IGNORECASE,
    ):
        inicio = hoy + timedelta(days=7 - hoy.weekday())
        return inicio, inicio + timedelta(days=6), "la proxima semana"

    if re.search(r"\b(?:este mes|mes actual)\b", texto, re.IGNORECASE):
        inicio = hoy.replace(day=1)
        if hoy.month == 12:
            siguiente = hoy.replace(year=hoy.year + 1, month=1, day=1)
        else:
            siguiente = hoy.replace(month=hoy.month + 1, day=1)
        return inicio, siguiente - timedelta(days=1), "este mes"

    if re.search(
        r"\b(?:mes que viene|proximo mes|siguiente mes)\b",
        texto,
        re.IGNORECASE,
    ):
        if hoy.month == 12:
            inicio = hoy.replace(year=hoy.year + 1, month=1, day=1)
        else:
            inicio = hoy.replace(month=hoy.month + 1, day=1)
        if inicio.month == 12:
            siguiente = inicio.replace(year=inicio.year + 1, month=1, day=1)
        else:
            siguiente = inicio.replace(month=inicio.month + 1, day=1)
        return inicio, siguiente - timedelta(days=1), "el proximo mes"

    if re.search(r"\bfin de semana\b", texto, re.IGNORECASE):
        sabado = hoy + timedelta(days=(5 - hoy.weekday()) % 7)
        return sabado, sabado + timedelta(days=1), "este fin de semana"

    return None


def _a_zona(valor: object, zona: object) -> datetime | None:
    """Convierte una fecha u hora a la zona horaria del usuario."""

    if isinstance(valor, datetime):
        return valor.astimezone(zona) if zona is not None else valor

    if isinstance(valor, str):
        try:
            fecha = datetime.fromisoformat(valor)
        except ValueError:
            return None
        return fecha.astimezone(zona) if zona is not None else fecha

    return None


def _texto_evento(evento: object, zona: object) -> str | None:
    """Formatea un evento para un listado natural."""

    if not isinstance(evento, dict):
        return None

    titulo = evento.get("titulo", "Evento")
    comienza = _a_zona(evento.get("comienza"), zona)
    termina = _a_zona(evento.get("termina"), zona)

    if comienza is None:
        return f"\u2022 {titulo}"

    texto = f"\u2022 {titulo} \u2014 {comienza.strftime('%d/%m/%Y %H:%M')}"

    if termina is not None:
        texto += f" a {termina.strftime('%H:%M')}"

    return texto


def _texto_evento_creado(evento: object, zona: object) -> str | None:
    """Formatea la confirmacion de un evento creado."""

    if not isinstance(evento, dict):
        return None

    titulo = evento.get("titulo", "Evento")
    comienza = _a_zona(evento.get("comienza"), zona)
    termina = _a_zona(evento.get("termina"), zona)

    if comienza is None:
        return f"Evento creado: {titulo}."

    texto = (
        f"Evento creado: {titulo}, "
        f"{comienza.strftime('%d/%m/%Y %H:%M')}"
    )

    if termina is not None:
        texto += f" a {termina.strftime('%H:%M')}"

    return texto + "."


def _detectar_accion(texto: str) -> dict[str, object] | None:
    """Detecta cancelaciones o completados de eventos con confirmacion."""

    cancelar = re.search(
        r"\b(?:cancela|cancelar|anula|anular)\s+(?:el\s+)?evento\s+(.+)",
        texto,
        re.IGNORECASE,
    )
    if cancelar is not None:
        titulo = cancelar.group(1).strip(" \t\n,.;:!?\u00bf\u00a1-")
        return {
            "herramienta": "agenda_cancelar_evento",
            "argumentos": {"evento_id": None, "titulo": titulo},
            "propuesta": (
                f"Voy a cancelar el evento '{titulo}'.\n\n"
                "Responde si para confirmar o no para cancelar."
            ),
        }

    completar = re.search(
        r"\b(?:marca como completado|completa|completar)\s+"
        r"(?:el\s+)?evento\s+(.+)",
        texto,
        re.IGNORECASE,
    )
    if completar is not None:
        titulo = completar.group(1).strip(" \t\n,.;:!?\u00bf\u00a1-")
        return {
            "herramienta": "agenda_completar_evento",
            "argumentos": {"evento_id": None, "titulo": titulo},
            "propuesta": (
                f"Voy a marcar como completado el evento '{titulo}'.\n\n"
                "Responde si para confirmar o no para cancelar."
            ),
        }

    return None
