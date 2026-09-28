import os
import json
import re
import hashlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse

# ============================================================
# CONFIGURACIÓN
# ============================================================

URL = "https://startup.proinnovate.gob.pe/concursos/"
ARCHIVO = "convocatorias.json"

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120 Safari/537.36"
    )
}


# ============================================================
# NORMALIZAR URL
# ============================================================

def normalizar_url(url):
    """
    Elimina fragmentos (#...) y parámetros innecesarios
    para evitar duplicados.
    """

    partes = urlparse(url)

    url_limpia = urlunparse(
        (
            partes.scheme,
            partes.netloc,
            partes.path,
            "",
            "",
            ""
        )
    )

    return url_limpia


# ============================================================
# OBTENER LISTADO DE CONVOCATORIAS
# ============================================================

def obtener_convocatorias():

    respuesta = requests.get(
        URL,
        headers=HEADERS,
        timeout=30
    )

    respuesta.raise_for_status()

    soup = BeautifulSoup(
        respuesta.text,
        "html.parser"
    )

    resultados = {}

    for enlace in soup.find_all("a", href=True):

        titulo = enlace.get_text(
            " ",
            strip=True
        )

        url = urljoin(
            URL,
            enlace["href"]
        )

        url = normalizar_url(url)

        if (
            titulo
            and "/concursos/" in url
            and url != URL
            and not url.startswith("mailto:")
        ):

            # Si la misma URL aparece varias veces,
            # intentamos conservar el título más informativo.

            if url not in resultados:

                resultados[url] = titulo

            elif len(titulo) > len(resultados[url]):

                resultados[url] = titulo

    return resultados


# ============================================================
# OBTENER CONTENIDO DE UNA CONVOCATORIA
# ============================================================

def obtener_contenido_convocatoria(url):

    try:

        respuesta = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        respuesta.raise_for_status()

        soup = BeautifulSoup(
            respuesta.text,
            "html.parser"
        )

        # Eliminamos contenido que puede cambiar sin que
        # realmente haya cambiado la convocatoria.

        for etiqueta in soup(
            [
                "script",
                "style",
                "noscript",
                "svg"
            ]
        ):

            etiqueta.decompose()

        # Intentamos centrarnos en el contenido principal.

        contenido = (
            soup.find("main")
            or soup.find("article")
            or soup.body
            or soup
        )

        texto = contenido.get_text(
            " ",
            strip=True
        )

        # Normalizar espacios
        texto = re.sub(
            r"\s+",
            " ",
            texto
        ).strip()

        # También guardamos enlaces importantes encontrados
        # dentro de la convocatoria.

        enlaces = []

        for enlace in contenido.find_all(
            "a",
            href=True
        ):

            href = enlace.get("href", "").strip()

            if not href:
                continue

            href = urljoin(
                url,
                href
            )

            href = normalizar_url(href)

            texto_enlace = enlace.get_text(
                " ",
                strip=True
            )

            # Nos interesan especialmente documentos,
            # bases, cronogramas y enlaces informativos.

            if (
                ".pdf" in href.lower()
                or "base" in texto_enlace.lower()
                or "cronograma" in texto_enlace.lower()
                or "resultado" in texto_enlace.lower()
                or "postula" in texto_enlace.lower()
                or "convocatoria" in texto_enlace.lower()
            ):

                enlaces.append(
                    f"{texto_enlace}|{href}"
                )

        enlaces = sorted(
            set(enlaces)
        )

        contenido_normalizado = (
            texto
            + "\n"
            + "\n".join(enlaces)
        )

        return contenido_normalizado

    except Exception as error:

        print(
            f"ERROR leyendo {url}: {error}"
        )

        return None


# ============================================================
# GENERAR HUELLA DIGITAL
# ============================================================

def generar_huella(contenido):

    if contenido is None:
        return None

    return hashlib.sha256(
        contenido.encode("utf-8")
    ).hexdigest()


# ============================================================
# CARGAR HISTORIAL
# ============================================================

def cargar_anteriores():

    if not os.path.exists(ARCHIVO):
        return {}

    try:

        with open(
            ARCHIVO,
            "r",
            encoding="utf-8"
        ) as archivo:

            datos = json.load(archivo)

            if isinstance(datos, dict):
                return datos

            return {}

    except Exception as error:

        print(
            f"Error leyendo {ARCHIVO}: {error}"
        )

        return {}


# ============================================================
# GUARDAR HISTORIAL
# ============================================================

def guardar_convocatorias(convocatorias):

    with open(
        ARCHIVO,
        "w",
        encoding="utf-8"
    ) as archivo:

        json.dump(
            convocatorias,
            archivo,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# TELEGRAM
# ============================================================

def enviar_mensaje_telegram(mensaje):

    if not BOT_TOKEN or not CHAT_ID:

        print(
            "Telegram no está configurado."
        )

        return False

    endpoint = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    try:

        respuesta = requests.post(
            endpoint,
            data={
                "chat_id": CHAT_ID,
                "text": mensaje,
                "disable_web_page_preview": False
            },
            timeout=30
        )

        respuesta.raise_for_status()

        print(
            "Mensaje enviado correctamente a Telegram."
        )

        return True

    except Exception as error:

        print(
            f"ERROR enviando mensaje a Telegram: {error}"
        )

        return False


# ============================================================
# ALERTA: NUEVA CONVOCATORIA
# ============================================================

def enviar_nueva_convocatoria(titulo, url):

    mensaje = (
        "🚨 NUEVA CONVOCATORIA PROINNÓVATE\n\n"
        f"📌 {titulo}\n\n"
        "🔎 Se detectó una nueva convocatoria "
        "publicada en ProInnóvate.\n\n"
        f"🔗 {url}"
    )

    enviar_mensaje_telegram(
        mensaje
    )


# ============================================================
# ALERTA: CAMBIO DE TÍTULO
# ============================================================

def enviar_cambio_titulo(
    titulo_anterior,
    titulo_nuevo,
    url
):

    mensaje = (
        "⚠️ CAMBIO DETECTADO EN PROINNÓVATE\n\n"
        "📌 Se modificó el título de una convocatoria.\n\n"
        "ANTES:\n"
        f"{titulo_anterior}\n\n"
        "AHORA:\n"
        f"{titulo_nuevo}\n\n"
        f"🔗 {url}"
    )

    enviar_mensaje_telegram(
        mensaje
    )


# ============================================================
# ALERTA: CAMBIO DE CONTENIDO
# ============================================================

def enviar_cambio_contenido(
    titulo,
    url
):

    mensaje = (
        "🔔 ACTUALIZACIÓN EN PROINNÓVATE\n\n"
        f"📌 {titulo}\n\n"
        "Se detectaron cambios dentro de esta convocatoria.\n\n"
        "🔎 Revisa posibles modificaciones en:\n"
        "📅 Fechas\n"
        "📆 Cronograma\n"
        "📄 Bases o documentos\n"
        "📋 Requisitos\n"
        "📝 Información de la convocatoria\n\n"
        f"🔗 {url}"
    )

    enviar_mensaje_telegram(
        mensaje
    )


# ============================================================
# CONVERTIR HISTORIAL ANTIGUO
# ============================================================

def historial_es_antiguo(datos):

    if not datos:
        return False

    for valor in datos.values():

        # Formato anterior:
        # URL -> "Título"

        if isinstance(valor, str):
            return True

    return False


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=========================================="
    )

    print(
        "MONITOR PROINNÓVATE"
    )

    print(
        "=========================================="
    )

    actuales = obtener_convocatorias()

    anteriores = cargar_anteriores()

    print(
        f"Convocatorias encontradas: "
        f"{len(actuales)}"
    )

    # --------------------------------------------------------
    # SEGURIDAD
    # --------------------------------------------------------

    if not actuales:

        print(
            "ADVERTENCIA: no se encontraron convocatorias."
        )

        print(
            "El historial NO será modificado."
        )

        return

    # --------------------------------------------------------
    # DETECTAR FORMATO ANTIGUO
    # --------------------------------------------------------

    migracion = historial_es_antiguo(
        anteriores
    )

    if migracion:

        print(
            "Historial antiguo detectado."
        )

        print(
            "Migrando al nuevo sistema de monitoreo..."
        )

        print(
            "NO se enviarán alertas de contenido "
            "durante esta migración."
        )

    # --------------------------------------------------------
    # NUEVO HISTORIAL
    # --------------------------------------------------------

    nuevo_historial = {}

    nuevas = 0
    cambios_titulo = 0
    cambios_contenido = 0
    errores_contenido = 0

    # --------------------------------------------------------
    # PROCESAR CADA CONVOCATORIA
    # --------------------------------------------------------

    for url, titulo in actuales.items():

        print(
            "------------------------------------------"
        )

        print(
            f"Revisando: {titulo}"
        )

        print(
            url
        )

        contenido = obtener_contenido_convocatoria(
            url
        )

        huella = generar_huella(
            contenido
        )

        # Si hubo un error leyendo la página,
        # intentamos conservar la huella anterior.

        if huella is None:

            errores_contenido += 1

            if (
                url in anteriores
                and isinstance(
                    anteriores[url],
                    dict
                )
            ):

                huella = anteriores[url].get(
                    "huella"
                )

        nuevo_historial[url] = {
            "titulo": titulo,
            "huella": huella
        }

        # ----------------------------------------------------
        # CONVOCATORIA NUEVA
        # ----------------------------------------------------

        if url not in anteriores:

            nuevas += 1

            print(
                f"NUEVA CONVOCATORIA: {titulo}"
            )

            # Si tenemos historial previo,
            # sí es una convocatoria realmente nueva.

            if anteriores:

                enviar_nueva_convocatoria(
                    titulo,
                    url
                )

            continue

        # ----------------------------------------------------
        # MIGRACIÓN DEL FORMATO ANTIGUO
        # ----------------------------------------------------

        if isinstance(
            anteriores[url],
            str
        ):

            titulo_anterior = anteriores[url]

            # Podemos detectar cambio de título,
            # pero NO cambio de contenido porque
            # todavía no existía una huella anterior.

            if (
                titulo_anterior.strip()
                != titulo.strip()
            ):

                cambios_titulo += 1

                print(
                    "Cambio de título detectado."
                )

                enviar_cambio_titulo(
                    titulo_anterior,
                    titulo,
                    url
                )

            continue

        # ----------------------------------------------------
        # FORMATO NUEVO
        # ----------------------------------------------------

        dato_anterior = anteriores[url]

        titulo_anterior = dato_anterior.get(
            "titulo",
            ""
        )

        huella_anterior = dato_anterior.get(
            "huella"
        )

        # ----------------------------------------------------
        # CAMBIO DE TÍTULO
        # ----------------------------------------------------

        if (
            titulo_anterior
            and titulo_anterior.strip()
            != titulo.strip()
        ):

            cambios_titulo += 1

            print(
                "CAMBIO DE TÍTULO DETECTADO."
            )

            enviar_cambio_titulo(
                titulo_anterior,
                titulo,
                url
            )

        # ----------------------------------------------------
        # CAMBIO DE CONTENIDO
        # ----------------------------------------------------

        if (
            huella_anterior
            and huella
            and huella_anterior != huella
        ):

            cambios_contenido += 1

            print(
                "CAMBIO DE CONTENIDO DETECTADO."
            )

            enviar_cambio_contenido(
                titulo,
                url
            )

    # --------------------------------------------------------
    # PRIMERA EJECUCIÓN TOTAL
    # --------------------------------------------------------

    if not anteriores:

        print(
            "Primera ejecución."
        )

        print(
            "Creando historial inicial sin enviar alertas."
        )

    # --------------------------------------------------------
    # MIGRACIÓN
    # --------------------------------------------------------

    if migracion:

        print(
            "Migración completada."
        )

        print(
            "Se crearon las huellas iniciales "
            "de las convocatorias."
        )

        print(
            "A partir de la próxima ejecución "
            "se detectarán cambios internos."
        )

    # --------------------------------------------------------
    # GUARDAR HISTORIAL
    # --------------------------------------------------------

    guardar_convocatorias(
        nuevo_historial
    )

    # --------------------------------------------------------
    # RESUMEN
    # --------------------------------------------------------

    print(
        "=========================================="
    )

    print(
        "RESUMEN"
    )

    print(
        "=========================================="
    )

    print(
        f"Convocatorias revisadas: {len(actuales)}"
    )

    print(
        f"Nuevas: {nuevas}"
    )

    print(
        f"Cambios de título: {cambios_titulo}"
    )

    print(
        f"Cambios de contenido: {cambios_contenido}"
    )

    print(
        f"Errores leyendo contenido: {errores_contenido}"
    )

    print(
        "Historial actualizado."
    )

    print(
        "Monitor finalizado correctamente."
    )


# ============================================================
# EJECUTAR
# ============================================================

if __name__ == "__main__":
    main()
    
