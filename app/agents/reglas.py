"""Reglas deterministas para las solicitudes personales frecuentes."""

import re
import unicodedata
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from uuid import UUID

from app.domain.lenguaje_fechas import (
    FechaHoraResuelta,
    HoraResuelta,
    resolver_fecha,
    resolver_fecha_hora,
    resolver_hora,
)
from app.agents.recordatorio_evento import detectar_recordatorio_de_evento
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
_DIAS_SEMANA = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "domingo": 6,
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
        self._eventos_recurrentes_pendientes: dict[UUID, list[dict[str, object]]] = {}
        self._conflictos_pendientes: dict[UUID, dict[str, object]] = {}

    def procesar(self, usuario_id: UUID, texto: str) -> dict[str, object] | None:
        """Resuelve una solicitud reconocida o devuelve ``None`` si no hay regla."""
        normalizado = _normalizar(texto)

        recurrentes = self._eventos_recurrentes_pendientes.get(usuario_id)
        if recurrentes is not None:
            if normalizado in {"si", "vale", "confirmo", "confirmar"}:
                self._eventos_recurrentes_pendientes.pop(usuario_id)
                creados = 0
                errores = []
                for argumentos in recurrentes:
                    resultado = self._herramientas.obtener(
                        "agenda_crear_evento"
                    ).ejecutar(usuario_id, argumentos)
                    if resultado.get("ok") is True:
                        creados += 1
                    else:
                        errores.append(
                            resultado.get(
                                "error",
                                "No se pudo crear un evento.",
                            )
                        )
                if errores:
                    return {
                        "ok": False,
                        "error": (
                            f"He creado {creados} eventos, pero no todos.\n"
                            + "\n".join(errores)
                        ),
                    }
                return {
                    "ok": True,
                    "datos": f"He creado {creados} eventos.",
                }
            if normalizado in {"no", "cancela", "cancelar"}:
                self._eventos_recurrentes_pendientes.pop(usuario_id)
                return {
                    "ok": True,
                    "datos": "He cancelado la creacion de los eventos.",
                }

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
        conflicto = self._conflictos_pendientes.get(usuario_id)
        if conflicto is not None:
            if conflicto.get("esperando_hora"):
                ahora_conflicto = self._ahora(usuario_id)
                evento = conflicto["evento_existente"]
                comienza_viejo = datetime.fromisoformat(evento["comienza"])
                termina_viejo = datetime.fromisoformat(evento["termina"])
                duracion = termina_viejo - comienza_viejo
                coincidencia = re.search(
                    r"a\s+las\s+(\d{1,2})(?::(\d{2}))?",
                    texto,
                    re.IGNORECASE,
                )
                if coincidencia is None:
                    return _preguntar("¿A qué hora quieres moverlo?")
                hora = int(coincidencia.group(1))
                minutos = int(coincidencia.group(2) or 0)
                nueva = datetime.combine(
                    comienza_viejo.date(),
                    time(hora, minutos),
                    tzinfo=ahora_conflicto.tzinfo,
                )
                self._conflictos_pendientes.pop(usuario_id)
                return self._herramientas.obtener(
                    "agenda_reprogramar_evento"
                ).ejecutar(
                    usuario_id,
                    {
                        "evento_id": evento["id"],
                        "comienza": nueva,
                        "termina": nueva + duracion,
                    },
                )

            if normalizado == "1":
                evento = conflicto["evento_existente"]
                nuevo = conflicto["evento_nuevo"]
                duracion = nuevo["termina"] - nuevo["comienza"]
                huecos = self._huecos_libres(
                    usuario_id,
                    nuevo["comienza"].date(),
                    duracion,
                    self._ahora(usuario_id).tzinfo,
                )
                lineas = ["Horas libres cercanas:"]
                for hueco in huecos:
                    lineas.append(f"• {hueco.strftime('%H:%M')}")
                return {"ok": True, "datos": "\n".join(lineas)}

            if normalizado == "2":
                conflicto["esperando_hora"] = True
                return _preguntar("¿A qué hora quieres moverlo?")

            if normalizado == "3":
                self._conflictos_pendientes.pop(usuario_id)
                cancelado = self._herramientas.obtener(
                    "agenda_cancelar_evento"
                ).ejecutar(
                    usuario_id,
                    {"evento_id": conflicto["evento_existente"]["id"]},
                )
                if cancelado.get("ok") is not True:
                    return cancelado
                return self._herramientas.obtener(
                    "agenda_crear_evento"
                ).ejecutar(
                    usuario_id,
                    conflicto["evento_nuevo"],
                )

            return _preguntar("Elige una opcion: 1, 2 o 3.")


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

        if _es_proxima_cita(normalizado):
            return self._consultar_proxima_cita(usuario_id)

        peticion_huecos = _detectar_huecos(
            normalizado,
            self._ahora(usuario_id),
        )
        if peticion_huecos is not None:
            if peticion_huecos.get("ok") is False:
                return peticion_huecos
            return self._consultar_huecos(usuario_id, peticion_huecos)

        consulta_evento = _detectar_consulta_evento(normalizado)
        if consulta_evento is not None:
            return self._consultar_evento(usuario_id, consulta_evento)
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

        cancelar_recordatorio = _detectar_cancelar_recordatorio(
            normalizado
        )
        if cancelar_recordatorio is not None:
            self._acciones_pendientes[usuario_id] = cancelar_recordatorio
            return {
                "ok": True,
                "datos": cancelar_recordatorio["propuesta"],
            }

        reprogramacion = _detectar_reprogramacion(
            normalizado,
            self._ahora(usuario_id),
            self._herramientas,
            usuario_id,
        )
        if reprogramacion is not None:
            if reprogramacion.get("ok") is False:
                return reprogramacion
            self._acciones_pendientes[usuario_id] = reprogramacion
            return {
                "ok": True,
                "datos": reprogramacion["propuesta"],
            }

        accion = _detectar_accion(normalizado)
        if accion is not None:
            self._acciones_pendientes[usuario_id] = accion
            return {"ok": True, "datos": accion["propuesta"]}

        recurrentes = self._detectar_eventos_recurrentes(
            usuario_id,
            normalizado,
            self._ahora(usuario_id),
        )
        if recurrentes is not None:
            if isinstance(recurrentes, dict) and recurrentes.get("ok") is False:
                return recurrentes
            self._eventos_recurrentes_pendientes[usuario_id] = recurrentes[
                "eventos"
            ]
            return {"ok": True, "datos": recurrentes["propuesta"]}

        recordatorio_evento = detectar_recordatorio_de_evento(
            self._herramientas,
            usuario_id,
            normalizado,
            self._ahora(usuario_id),
        )
        if recordatorio_evento is not None:
            self._acciones_pendientes[usuario_id] = recordatorio_evento
            return {
                "ok": True,
                "datos": recordatorio_evento["propuesta"],
            }

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

    def _consultar_evento(
        self,
        usuario_id: UUID,
        titulo: str,
    ) -> dict[str, object] | None:
        """Consulta un evento por titulo y lo presenta en lenguaje natural."""

        try:
            resultado = self._herramientas.obtener(
                "agenda_consultar_evento"
            ).ejecutar(
                usuario_id,
                {"evento_id": None, "titulo": titulo},
            )
        except KeyError:
            return None

        if resultado.get("ok") is not True:
            return resultado

        evento = resultado.get("datos")
        if not isinstance(evento, dict):
            return resultado

        zona = self._ahora(usuario_id).tzinfo
        comienza = datetime.fromisoformat(
            evento["comienza"]
        ).astimezone(zona)
        termina = datetime.fromisoformat(
            evento["termina"]
        ).astimezone(zona)

        texto = (
            f"{evento['titulo']} es el "
            f"{comienza.strftime('%d/%m/%Y')} de "
            f"{comienza.strftime('%H:%M')} a "
            f"{termina.strftime('%H:%M')}."
        )

        if evento.get("ubicacion"):
            texto += f"\nLugar: {evento['ubicacion']}"

        if evento.get("descripcion"):
            texto += f"\nNotas: {evento['descripcion']}"

        return {"ok": True, "datos": texto}

    def _consultar_proxima_cita(self, usuario_id: UUID) -> dict[str, object]:
        """Consulta y presenta el siguiente evento activo."""

        ahora = self._ahora(usuario_id)
        try:
            resultado = self._herramientas.obtener(
                "agenda_proximo_evento"
            ).ejecutar(usuario_id, {"ahora": ahora})
        except KeyError:
            return None

        if resultado.get("ok") is not True:
            return resultado

        evento = resultado.get("datos")
        if not evento:
            return {"ok": True, "datos": "No tienes eventos proximos."}

        comienza = datetime.fromisoformat(
            evento["comienza"]
        ).astimezone(ahora.tzinfo)
        termina = datetime.fromisoformat(
            evento["termina"]
        ).astimezone(ahora.tzinfo)
        duracion = int((termina - comienza).total_seconds() // 60)

        return {
            "ok": True,
            "datos": (
                f"Tu proxima cita es {evento['titulo']} el "
                f"{comienza.strftime('%d/%m/%Y')} a las "
                f"{comienza.strftime('%H:%M')} durante {duracion} minutos."
            ),
        }

    def _consultar_huecos(
        self,
        usuario_id: UUID,
        peticion: dict[str, object],
    ) -> dict[str, object]:
        """Consulta y presenta los huecos libres de una franja."""

        try:
            resultado = self._herramientas.obtener(
                "agenda_huecos_libres"
            ).ejecutar(usuario_id, peticion)
        except KeyError:
            return None

        if resultado.get("ok") is not True:
            return resultado

        huecos = resultado.get("datos") or []
        if not huecos:
            return {
                "ok": True,
                "datos": "No encuentro huecos libres en esa franja.",
            }

        lineas = ["Huecos libres:"]

        zona = self._ahora(usuario_id).tzinfo

        for hueco in huecos:
            desde = datetime.fromisoformat(
                hueco["comienza"]
            ).astimezone(zona)
            hasta = datetime.fromisoformat(
                hueco["termina"]
            ).astimezone(zona)
            lineas.append(
                f"• {desde.strftime('%H:%M')} a {hasta.strftime('%H:%M')}"
            )

        return {"ok": True, "datos": "\n".join(lineas)}

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

    def _hay_duplicado_proximo(
        self,
        usuario_id: UUID,
        titulo: str,
        desde: date,
    ) -> bool:
        """Comprueba si hay otro evento con el mismo titulo en los proximos 6 dias."""

        try:
            herramienta_dia = self._herramientas.obtener(
                "agenda_eventos_del_dia"
            )
        except KeyError:
            return False

        for offset in range(-6, 7):
            dia = desde + timedelta(days=offset)
            existentes = herramienta_dia.ejecutar(
                usuario_id,
                {"dia": dia},
            )
            if existentes.get("ok") is not True:
                continue

            for evento in existentes.get("datos") or []:
                if not isinstance(evento, dict):
                    continue
                nombre = str(evento.get("titulo", "")).strip().lower()
                if nombre == titulo.lower():
                    return True

        return False

    def _huecos_libres(
        self,
        usuario_id: UUID,
        dia: date,
        duracion: timedelta,
        zona: object,
    ) -> list[datetime]:
        """Devuelve hasta tres huecos libres cercanos en el dia indicado."""

        try:
            herramienta_dia = self._herramientas.obtener(
                "agenda_eventos_del_dia"
            )
        except KeyError:
            return []

        resultado = herramienta_dia.ejecutar(usuario_id, {"dia": dia})
        eventos = resultado.get("datos") or [] if resultado.get("ok") else []

        ocupados = []
        for evento in eventos:
            if not isinstance(evento, dict):
                continue
            inicio = _a_zona(evento.get("comienza"), zona)
            fin = _a_zona(evento.get("termina"), zona)
            if inicio is not None and fin is not None:
                ocupados.append((inicio, fin))

        candidatos = []
        duracion_minutos = int(duracion.total_seconds() // 60)

        for minuto in range(8 * 60, 22 * 60 - duracion_minutos + 1, 30):
            comienza = datetime.combine(
                dia,
                time(minuto // 60, minuto % 60),
                tzinfo=zona,
            )
            termina = comienza + duracion

            libre = True
            for inicio_evento, fin_evento in ocupados:
                if comienza < fin_evento and termina > inicio_evento:
                    libre = False
                    break

            if libre:
                candidatos.append(comienza)

        candidatos.sort(
            key=lambda candidato: abs(
                (candidato - comienza).total_seconds()
            )
        )
        return candidatos[:3]

    def _detectar_eventos_recurrentes(
        self,
        usuario_id: UUID,
        texto: str,
        ahora: datetime,
    ) -> dict[str, object] | None:
        """Detecta varios dias para un mismo evento y propone su creacion."""

        patron = re.compile(
            r"(?:crea(?:r)?\s+)?(?:un\s+)?(?:evento\s+)?"
            r"(?P<titulo>.+?)\s+"
            r"(?P<dias>lunes|martes|miercoles|jueves|viernes|sabado|domingo)"
            r"(?:\s*(?:,|y)\s*(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo))*"
            r"\s+a\s+las\s+(?P<hora>\d{1,2})(?::(?P<minutos>\d{2}))?"
            r"(?:\s+durante\s+(?P<cantidad>\d+)\s+horas?)?",
            re.IGNORECASE,
        )
        coincidencia = patron.search(texto)

        if coincidencia is None:
            return None

        titulo = coincidencia.group("titulo").strip()
        nombres_dias = re.findall(
            r"lunes|martes|miercoles|jueves|viernes|sabado|domingo",
            coincidencia.group(0),
            re.IGNORECASE,
        )
        dias = sorted({_DIAS_SEMANA[nombre] for nombre in nombres_dias})

        if not dias:
            return None

        hora = int(coincidencia.group("hora"))
        minutos = int(coincidencia.group("minutos") or 0)
        cantidad = int(coincidencia.group("cantidad") or 1)
        duracion = timedelta(hours=cantidad)

        try:
            herramienta_dia = self._herramientas.obtener(
                "agenda_eventos_del_dia"
            )
        except KeyError:
            herramienta_dia = None

        eventos = []

        for numero_dia in dias:
            diferencia = (numero_dia - ahora.weekday()) % 7
            fecha = ahora.date() + timedelta(days=diferencia)
            comienza = datetime.combine(
                fecha,
                time(hora, minutos),
                tzinfo=ahora.tzinfo,
            )

            if comienza <= ahora:
                fecha += timedelta(days=7)
                comienza = datetime.combine(
                    fecha,
                    time(hora, minutos),
                    tzinfo=ahora.tzinfo,
                )

            termina = comienza + duracion

            if herramienta_dia is not None:
                existentes = herramienta_dia.ejecutar(
                    usuario_id,
                    {"dia": fecha},
                )
                for evento in existentes.get("datos") or []:
                    if not isinstance(evento, dict):
                        continue
                    inicio_evento = _a_zona(
                        evento.get("comienza"),
                        ahora.tzinfo,
                    )
                    fin_evento = _a_zona(
                        evento.get("termina"),
                        ahora.tzinfo,
                    )
                    if inicio_evento is None or fin_evento is None:
                        continue
                    if comienza < fin_evento and termina > inicio_evento:
                        return {
                            "ok": False,
                            "error": (
                                f"Ya tienes '{evento.get('titulo', 'un evento')}' "
                                f"de {inicio_evento.strftime('%H:%M')} a "
                                f"{fin_evento.strftime('%H:%M')} el "
                                f"{fecha.strftime('%d/%m/%Y')}.\n"
                                "Elige otro horario o cancela el evento existente."
                            ),
                        }

            eventos.append(
                {
                    "titulo": titulo,
                    "comienza": comienza,
                    "termina": termina,
                }
            )

        lineas = [f"Voy a crear estos {len(eventos)} eventos:"]

        for evento in eventos:
            comienza = evento["comienza"]
            termina = evento["termina"]
            lineas.append(
                f"\u2022 {evento['titulo']} \u2014 "
                f"{comienza.strftime('%d/%m/%Y %H:%M')} a "
                f"{termina.strftime('%H:%M')}"
            )

        lineas.append("")
        lineas.append("Responde si para confirmar los tres o no para cancelar.")

        return {
            "eventos": eventos,
            "propuesta": "\n".join(lineas),
        }

    def _crear_evento(self, usuario_id: UUID, texto: str) -> dict[str, object]:
        """Crea un evento y propone opciones cuando hay un conflicto."""
        ahora = self._ahora(usuario_id)
        if ahora is None:
            return _preguntar("¿Qué día y a qué hora quieres el evento?")
        resuelta = self._resolver_fecha_hora(texto, ahora)
        if isinstance(resuelta, dict):
            return resuelta
        fecha_hora = resuelta
        if fecha_hora.hora is None:
            return _preguntar("¿A qué hora quieres que empiece el evento?")
        titulo, lugar, notas = _detalles_evento(texto)
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

        mismo_nombre = False

        if herramienta_dia is not None:
            for offset in range(7):
                dia = comienza.date() + timedelta(days=offset)
                existentes = herramienta_dia.ejecutar(
                    usuario_id,
                    {"dia": dia},
                )
                if existentes.get("ok") is not True:
                    continue

                for evento in existentes.get("datos") or []:
                    if not isinstance(evento, dict):
                        continue

                    inicio_evento = _a_zona(
                        evento.get("comienza"),
                        ahora.tzinfo,
                    )
                    fin_evento = _a_zona(
                        evento.get("termina"),
                        ahora.tzinfo,
                    )

                    if inicio_evento is None or fin_evento is None:
                        continue

                    if comienza < fin_evento and termina > inicio_evento:
                        argumentos = {
                            "titulo": titulo,
                            "comienza": comienza,
                            "termina": termina,
                        }
                        if lugar:
                            argumentos["ubicacion"] = lugar
                        if notas:
                            argumentos["descripcion"] = notas

                        self._conflictos_pendientes[usuario_id] = {
                            "evento_nuevo": argumentos,
                            "evento_existente": evento,
                        }

                        return {
                            "ok": True,
                            "datos": (
                                f"Ya tienes "
                                f"'{evento.get('titulo', 'un evento')}' de "
                                f"{inicio_evento.strftime('%H:%M')} a "
                                f"{fin_evento.strftime('%H:%M')} ese dia.\n\n"
                                "1. Elegir otra hora\n"
                                "2. Mover el evento existente\n"
                                "3. Cancelar el existente\n\n"
                                "Elige una opcion (1, 2 o 3)."
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
        if lugar:
            argumentos["ubicacion"] = lugar
        if notas:
            argumentos["descripcion"] = notas

        self._eventos_pendientes[usuario_id] = argumentos

        if duracion.total_seconds() % 3600 == 0:
            duracion_texto = f"{int(duracion.total_seconds() // 3600)} hora(s)"
        else:
            duracion_texto = f"{int(duracion.total_seconds() // 60)} minutos"

        mismo_nombre = mismo_nombre or self._hay_duplicado_proximo(
            usuario_id,
            titulo,
            comienza.date(),
        )

        detalles = ""
        if lugar:
            detalles += f"\n• Lugar: {lugar}"
        if notas:
            detalles += f"\n• Notas: {notas}"

        aviso = ""
        if mismo_nombre:
            aviso = "\n\nYa tienes un evento con ese nombre ese dia."

        propuesta = (
            "Voy a crear este evento:\n"
            f"• {titulo.capitalize()}\n"
            f"• {comienza.strftime('%d/%m/%Y %H:%M')}\n"
            f"• Duracion: {duracion_texto}"
            f"{detalles}"
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
        argumentos = {
            "mensaje": mensaje,
            "cuando": cuando,
        }
        self._acciones_pendientes[usuario_id] = {
            "herramienta": "recordatorios_programar",
            "argumentos": argumentos,
            "propuesta": (
                f"Voy a programar el recordatorio '{mensaje}' para el "
                f"{cuando.strftime('%d/%m/%Y %H:%M')}.\n\n"
                "Responde si para confirmar o no para cancelar."
            ),
        }
        return {
            "ok": True,
            "datos": self._acciones_pendientes[usuario_id]["propuesta"],
        }

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


def _detalles_evento(texto: str) -> tuple[str, str, str]:
    """Separa el titulo, el lugar y las notas de una peticion de evento."""
    resto = _limpiar_tiempos(texto)
    notas = ""
    lugar = ""

    etiqueta = re.search(
        r"\bnotas?:\s*(?P<notas>.+)$",
        resto,
        re.IGNORECASE,
    )
    if etiqueta:
        notas = etiqueta.group("notas").strip()
        resto = resto[: etiqueta.start()].strip().rstrip(", ")

    coincidencia = re.search(
        r"\ben\s+(?:la\s+|el\s+|los\s+|las\s+)?(?P<lugar>.+)$",
        resto,
        re.IGNORECASE,
    )
    if coincidencia:
        lugar = coincidencia.group("lugar").strip()
        resto = resto[: coincidencia.start()].strip()

    if lugar and not notas:
        partes = lugar.split(",", 1)
        if len(partes) == 2:
            lugar = partes[0].strip()
            notas = partes[1].strip()

    titulo = _titulo_evento(resto)
    return titulo, lugar, notas


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

    titulo = str(evento.get("titulo", "Evento"))
    titulo = titulo[:1].upper() + titulo[1:]
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

    titulo = str(evento.get("titulo", "Evento"))
    titulo = titulo[:1].upper() + titulo[1:]
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


def _detectar_cancelar_recordatorio(texto: str) -> dict[str, object] | None:
    """Detecta la cancelacion de un recordatorio por su mensaje."""

    coincidencia = re.search(
        r"\b(?:cancela|cancelar|anula|anular)\s+"
        r"(?:el\s+)?recordatorio\s+(.+)",
        texto,
        re.IGNORECASE,
    )

    if coincidencia is None:
        return None

    mensaje = coincidencia.group(1).strip(" \t\n,.;:!?\u00bf\u00a1-")

    return {
        "herramienta": "recordatorios_cancelar",
        "argumentos": {"recordatorio_id": None, "mensaje": mensaje},
        "propuesta": (
            f"Voy a cancelar el recordatorio '{mensaje}'.\n\n"
            "Responde si para confirmar o no para cancelar."
        ),
    }


def _detectar_reprogramacion(
    texto: str,
    ahora: datetime,
    herramientas: object,
    usuario_id: object,
) -> dict[str, object] | None:
    """Detecta el cambio de fecha u hora de un evento existente."""

    coincidencia = re.search(
        r"\b(?:mueve|mover|reprograma|reprogramar|cambia|cambiar)\s+"
        r"(?:el\s+)?evento\s+(?P<titulo>.+?)\s+"
        r"(?:al|para el|el)\s+(?P<resto>.+)$",
        texto,
        re.IGNORECASE,
    )

    if coincidencia is None:
        return None

    titulo = coincidencia.group("titulo").strip(" \t\n,.;:!?\u00bf\u00a1-")
    resto = coincidencia.group("resto") or ""

    fecha = resolver_fecha(resto, ahora)
    if fecha is None:
        return _preguntar(
            "¿Qué día quieres para el evento? Indica una fecha que pueda resolver."
        )

    hora = resolver_hora(resto)
    if hora is None:
        return _preguntar("¿A qué hora quieres el evento?")

    duracion = _duracion_explicita(resto)

    if duracion is None:
        try:
            original = herramientas.obtener(
                "agenda_consultar_evento"
            ).ejecutar(
                usuario_id,
                {"evento_id": None, "titulo": titulo},
            )
        except KeyError:
            original = None

        if (
            original is None
            or original.get("ok") is not True
            or not isinstance(original.get("datos"), dict)
        ):
            return _preguntar(
                "¿Cuánto durará el evento o a qué hora terminará?"
            )

        datos = original["datos"]
        comienza_original = datetime.fromisoformat(datos["comienza"])
        termina_original = datetime.fromisoformat(datos["termina"])
        duracion = termina_original - comienza_original

    comienza = datetime.combine(
        fecha,
        hora.hora,
        tzinfo=ahora.tzinfo,
    )
    termina = comienza + duracion

    return {
        "herramienta": "agenda_reprogramar_evento",
        "argumentos": {
            "evento_id": None,
            "titulo": titulo,
            "comienza": comienza,
            "termina": termina,
        },
        "propuesta": (
            f"Voy a mover el evento '{titulo}' al "
            f"{comienza.strftime('%d/%m/%Y %H:%M')} a "
            f"{termina.strftime('%H:%M')}.\n\n"
            "Responde si para confirmar o no para cancelar."
        ),
    }


def _es_proxima_cita(texto: str) -> bool:
    """Detecta consultas sobre el siguiente evento."""

    return re.search(
        r"\b(?:cual es mi proxima cita|proxima cita|proximo evento|"
        r"que tengo ahora)\b",
        texto,
        re.IGNORECASE,
    ) is not None


def _detectar_huecos(
    texto: str,
    ahora: datetime,
) -> dict[str, object] | None:
    """Detecta una consulta de huecos libres en una franja."""

    coincidencia = re.search(
        r"\bhuecos?(?:\s+libres)?(?:\s+(?:el|para el|del|para)\s+"
        r"(?P<resto>.+))?$",
        texto,
        re.IGNORECASE,
    )

    if coincidencia is None:
        return None

    resto = coincidencia.group("resto") or ""
    fecha = resolver_fecha(resto, ahora) if resto else None

    if fecha is None:
        return _preguntar(
            "¿De qué día quieres consultar los huecos libres?"
        )

    franja = re.search(
        r"\bde\s+(?P<desde>.+?)\s+a\s+(?P<hasta>.+)$",
        resto,
        re.IGNORECASE,
    )

    if franja is None:
        desde_texto = "09:00"
        hasta_texto = "21:00"
    else:
        desde_texto = franja.group("desde").strip()
        hasta_texto = franja.group("hasta").strip()

    if re.fullmatch(r"\d{1,2}", desde_texto):
        desde_texto += ":00"

    if re.fullmatch(r"\d{1,2}", hasta_texto):
        hasta_texto += ":00"

    desde_hora = resolver_hora(f"a las {desde_texto}")
    hasta_hora = resolver_hora(f"a las {hasta_texto}")

    if desde_hora is None or hasta_hora is None:
        return _preguntar(
            "¿Entre qué horas quieres consultar los huecos libres?"
        )

    return {
        "dia": fecha,
        "desde": datetime.combine(
            fecha,
            desde_hora.hora,
            tzinfo=ahora.tzinfo,
        ),
        "hasta": datetime.combine(
            fecha,
            hasta_hora.hora,
            tzinfo=ahora.tzinfo,
        ),
        "minutos": 30,
    }


def _detectar_consulta_evento(texto: str) -> str | None:
    """Detecta consultas del tipo: cuando tengo el dentista."""

    coincidencia = re.search(
        r"\b(?:cuando tengo|cuando es)\s+(?:el\s+)?"
        r"(?P<titulo>.+?)\??$",
        texto,
        re.IGNORECASE,
    )

    if coincidencia is None:
        return None

    return coincidencia.group("titulo").strip(" \t\n,.;:!?\u00bf\u00a1-")
