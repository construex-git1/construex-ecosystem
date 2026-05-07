"""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN 6.0.0 (COMPLETA)
======================================================================
"""

import os
import re
import json
import requests
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# ============================================
# CONFIGURACION BASICA (SIN IA PARA PRUEBAS)
# ============================================

WHATSAPP_VERIFY_TOKEN = "construex_verify_2026"

# Directorios
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATEGORIAS_DIR = {
    "Salud": os.path.join(BASE_DIR, "contenido", "Salud"),
    "Emprendimiento": os.path.join(BASE_DIR, "contenido", "Emprendimiento"),
    "Automejora": os.path.join(BASE_DIR, "contenido", "Automejora"),
    "Construccion": os.path.join(BASE_DIR, "contenido", "Construccion"),
    "Construex University": os.path.join(BASE_DIR, "contenido", "Construex_University")
}

for carpeta in CATEGORIAS_DIR.values():
    os.makedirs(carpeta, exist_ok=True)

HIGGSFIELD_DIR = os.path.join(BASE_DIR, "higgsfield_prompts")
os.makedirs(HIGGSFIELD_DIR, exist_ok=True)

DB_FILE = os.path.join(BASE_DIR, "construex.db")
url_cache = {}


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contenido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            url TEXT,
            titulo TEXT,
            dominio TEXT,
            categoria TEXT,
            subcategoria TEXT,
            viralidad INTEGER,
            resumen TEXT,
            archivo_resumen TEXT,
            archivo_higgsfield TEXT,
            procesado BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()


def extraer_enlaces(texto):
    patron_url = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(patron_url, texto)


def leer_contenido_url(url):
    if url in url_cache:
        return url_cache[url]

    resultado = {
        'url': url,
        'titulo': '',
        'descripcion': '',
        'dominio': urlparse(url).netloc,
        'exito': False
    }

    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.text, 'html.parser')

        if soup.find('title'):
            resultado['titulo'] = soup.find('title').text.strip()[:200]

        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            resultado['descripcion'] = meta_desc.get('content', '')[:500]

        if not resultado['descripcion']:
            for script in soup(["script", "style"]):
                script.decompose()
            texto = soup.get_text()
            texto = ' '.join(texto.split())
            resultado['descripcion'] = texto[:500]

        resultado['exito'] = True
        url_cache[url] = resultado
    except Exception as e:
        resultado['error'] = str(e)

    return resultado


def clasificar_manual(titulo, descripcion, dominio):
    texto = f"{titulo} {descripcion}".lower()
    if any(p in texto for p in ["arquitect", "construc", "obra", "cemento", "archdaily"]):
        return "Construccion", "General", 7
    elif any(p in texto for p in ["negocio", "emprend", "empresa", "ventas"]):
        return "Emprendimiento", "General", 7
    elif any(p in texto for p in ["curso", "aprender", "educacion"]):
        return "Construex University", "General", 6
    elif any(p in texto for p in ["salud", "medico", "bienestar"]):
        return "Salud", "General", 6
    return "Automejora", "General", 5


def guardar_resumen(titulo, categoria, subcategoria, resumen, url):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
    filename = f"{timestamp}_{nombre_limpio}.md"

    carpeta_base = CATEGORIAS_DIR.get(categoria, CATEGORIAS_DIR["Automejora"])
    carpeta_sub = os.path.join(carpeta_base, subcategoria)
    os.makedirs(carpeta_sub, exist_ok=True)
    filepath = os.path.join(carpeta_sub, filename)

    contenido = f"""---
title: {titulo}
source: {url}
date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
category: {categoria}
subcategory: {subcategoria}
---

{resumen}
"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(contenido)

    return filepath


def guardar_prompt_higgsfield(titulo, categoria, subcategoria, url):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
    filename = f"{timestamp}_{nombre_limpio}.json"
    filepath = os.path.join(HIGGSFIELD_DIR, filename)

    prompt_data = {
        "video_prompt": f"Video educativo sobre {categoria}: {titulo[:100]}",
        "duration": 20,
        "aspect_ratio": "9:16",
        "style": "educational",
        "text_overlay": f"Aprende sobre {categoria}"
    }
    contenido = {
        "metadata": {
            "source_url": url,
            "category": categoria,
            "subcategory": subcategoria,
            "fecha": datetime.now().isoformat(),
            "titulo": titulo
        },
        "prompt": prompt_data
    }
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(contenido, f, ensure_ascii=False, indent=2)
    return filepath


def guardar_en_db(url, titulo, dominio, categoria, subcategoria, viralidad, resumen, archivo_resumen, archivo_higgsfield):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO contenido (
            fecha, url, titulo, dominio, categoria, subcategoria, viralidad,
            resumen, archivo_resumen, archivo_higgsfield, procesado
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().isoformat(),
        url,
        titulo[:200],
        dominio,
        categoria,
        subcategoria,
        viralidad,
        resumen[:500],
        archivo_resumen,
        archivo_higgsfield,
        1
    ))
    conn.commit()
    conn.close()


def procesar_enlace_completo(url):
    print(f"\n📡 Procesando: {url[:80]}...")

    contenido = leer_contenido_url(url)
    if not contenido['exito']:
        return {"error": "No se pudo acceder", "url": url}

    categoria, subcategoria, viralidad = clasificar_manual(
        contenido['titulo'],
        contenido['descripcion'],
        contenido['dominio']
    )

    print(f"   📁 Categoria: {categoria} > {subcategoria}")

    resumen = f"Resumen de '{contenido['titulo']}': {contenido['descripcion']}"

    archivo_resumen = guardar_resumen(
        contenido['titulo'],
        categoria,
        subcategoria,
        resumen,
        url
    )

    archivo_higgsfield = guardar_prompt_higgsfield(
        contenido['titulo'],
        categoria,
        subcategoria,
        url
    )

    guardar_en_db(
        url,
        contenido['titulo'],
        contenido['dominio'],
        categoria,
        subcategoria,
        viralidad,
        resumen,
        archivo_resumen,
        archivo_higgsfield
    )

    return {
        "exito": True,
        "url": url,
        "titulo": contenido['titulo'],
        "categoria": categoria,
        "subcategoria": subcategoria,
        "viralidad": viralidad,
        "archivo_resumen": archivo_resumen,
        "archivo_higgsfield": archivo_higgsfield
    }


# ============================================
# ENDPOINTS
# ============================================

@app.route('/')
def home():
    return jsonify({
        "servicio": "Construex Ecosystem",
        "estado": "activo",
        "version": "6.0.0",
        "funcionalidades": [
            "Procesamiento de enlaces",
            "Clasificacion manual",
            "Generacion de resumenes",
            "Generacion de prompts para Higgsfield"
        ]
    })


@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode and token and token == WHATSAPP_VERIFY_TOKEN:
        return challenge, 200
    return 'Forbidden', 403


@app.route('/webhook', methods=['POST'])
def receive_whatsapp():
    return jsonify({"status": "ok"}), 200


@app.route('/procesar', methods=['POST'])
def procesar():
    data = request.get_json()
    mensaje = data.get('mensaje', '')
    if not mensaje:
        return jsonify({"error": "No hay mensaje"}), 400
    enlaces = extraer_enlaces(mensaje)
    if not enlaces:
        return jsonify({"error": "No se encontraron enlaces"}), 400
    resultado = procesar_enlace_completo(enlaces[0])
    return jsonify(resultado), 200


@app.route('/estructura', methods=['GET'])
def ver_estructura():
    estructura = {}
    for cat, path in CATEGORIAS_DIR.items():
        if os.path.exists(path):
            estructura[cat] = os.listdir(path) if os.listdir(path) else []
    return jsonify({"estructura": estructura}), 200


@app.route('/higgsfield', methods=['GET'])
def listar_higgsfield():
    archivos = os.listdir(HIGGSFIELD_DIR) if os.path.exists(HIGGSFIELD_DIR) else []
    return jsonify({"prompts_higgsfield": archivos[-20:]})


@app.route('/estadisticas', methods=['GET'])
def estadisticas():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM contenido")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT categoria, COUNT(*) FROM contenido GROUP BY categoria")
    stats = dict(cursor.fetchall())
    conn.close()
    return jsonify({"total": total, "por_categoria": stats})


@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    init_db()
    print("""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN OPERATIVA
======================================================================
""")
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)