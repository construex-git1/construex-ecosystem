"""
======================================================================
         CONSTRUEX ECOSYSTEM - COMPLETO (Gemini + Grok + Higgsfield)
======================================================================
"""

import os
import re
import json
import requests
import sqlite3
import time
from datetime import datetime
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# ============================================
# CONFIGURACION
# ============================================

WHATSAPP_VERIFY_TOKEN = "construex_verify_2026"

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    gemini_model = None

# Grok
GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

# Higgsfield
HIGGSFIELD_API_KEY = os.getenv("HIGGSFIELD_API_KEY")
HIGGSFIELD_API_SECRET = os.getenv("HIGGSFIELD_API_SECRET")
HIGGSFIELD_API_URL = "https://api.higgsfield.ai/v1/generate"

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

VIDEOS_DIR = os.path.join(BASE_DIR, "videos_generados")
os.makedirs(VIDEOS_DIR, exist_ok=True)

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
            prompt_higgsfield TEXT,
            archivo_higgsfield TEXT,
            video_url TEXT,
            motor_ia TEXT,
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
        'es_x_twitter': 'twitter.com' in url or 'x.com' in url,
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


def clasificar_con_gemini(titulo, descripcion, dominio):
    if not gemini_model:
        return None

    prompt = f"""
    Clasifica este contenido en UNA de estas categorias:
    Salud, Emprendimiento, Automejora, Construccion, Construex University

    TITULO: {titulo}
    DOMINIO: {dominio}
    DESCRIPCION: {descripcion[:500]}

    Responde SOLO con JSON: {{"categoria": "nombre", "subcategoria": "nombre", "viralidad": 7}}
    """

    try:
        respuesta = gemini_model.generate_content(prompt)
        texto = respuesta.text
        if "```json" in texto:
            texto = texto.split("```json")[1].split("```")[0]
        return json.loads(texto.strip())
    except Exception as e:
        print(f"Error Gemini: {e}")
        return None


def clasificar_con_grok(titulo, descripcion, dominio):
    if not GROK_API_KEY:
        return None

    prompt = f"""
    Clasifica el siguiente contenido en UNA de estas categorías:
    Salud, Emprendimiento, Automejora, Construccion, Construex University

    Título: {titulo}
    Dominio: {dominio}
    Descripción: {descripcion[:500]}

    Responde SOLO con formato JSON: 
    {{"categoria": "nombre", "subcategoria": "nombre", "viralidad": 7}}
    """

    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "grok-1.5",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 150
    }

    try:
        response = requests.post(GROK_API_URL, headers=headers, json=data, timeout=15)
        resultado = response.json()
        respuesta_texto = resultado['choices'][0]['message']['content']

        if "```json" in respuesta_texto:
            respuesta_texto = respuesta_texto.split("```json")[1].split("```")[0]

        return json.loads(respuesta_texto)
    except Exception as e:
        print(f"Error Grok: {e}")
        return None


def clasificar_contenido(titulo, descripcion, dominio, es_x_twitter=False):
    resultado = None

    if es_x_twitter and GROK_API_KEY:
        print("   🔍 Usando Grok (X/Twitter)...")
        resultado = clasificar_con_grok(titulo, descripcion, dominio)

    if not resultado and gemini_model:
        print("   🔍 Usando Gemini...")
        resultado = clasificar_con_gemini(titulo, descripcion, dominio)

    if not resultado:
        print("   ⚠️ Fallback a clasificación manual")
        texto = f"{titulo} {descripcion}".lower()
        if any(p in texto for p in ["construc", "arquitect", "obra", "cemento", "archdaily"]):
            return {"categoria": "Construccion", "subcategoria": "Proyectos", "viralidad": 7}
        elif any(p in texto for p in ["negocio", "emprend", "empresa", "ventas", "startup"]):
            return {"categoria": "Emprendimiento", "subcategoria": "Negocios", "viralidad": 7}
        elif any(p in texto for p in ["curso", "aprender", "educacion", "certificacion", "taller"]):
            return {"categoria": "Construex University", "subcategoria": "Cursos", "viralidad": 6}
        elif any(p in texto for p in ["salud", "medico", "bienestar", "dieta", "ejercicio"]):
            return {"categoria": "Salud", "subcategoria": "Bienestar", "viralidad": 6}
        else:
            return {"categoria": "Automejora", "subcategoria": "Crecimiento", "viralidad": 5}

    return resultado


def generar_resumen_notebooklm(titulo, descripcion, dominio, categoria, subcategoria):
    if not gemini_model:
        return f"Resumen de '{titulo}': {descripcion[:500]}"

    prompt = f"""
    Genera un resumen educativo estructurado para Notebook LM.

    TITULO: {titulo}
    CATEGORIA: {categoria}
    SUBCATEGORIA: {subcategoria}
    FUENTE: {dominio}
    CONTENIDO: {descripcion[:1500]}

    FORMATO EXACTO:
    ============================================================
    TITULO: {titulo}
    CATEGORIA: {categoria}
    SUBCATEGORIA: {subcategoria}
    FUENTE: {dominio}
    
    RESUMEN EJECUTIVO:
    [2-3 párrafos]
    
    PUNTOS CLAVE:
    1. [primer punto]
    2. [segundo punto]
    3. [tercer punto]
    
    APLICACION PRACTICA:
    [Cómo aplicar este conocimiento]
    ============================================================
    """

    try:
        respuesta = gemini_model.generate_content(prompt)
        return respuesta.text
    except:
        return f"Resumen no disponible para {titulo}"


def generar_prompt_higgsfield(titulo, resumen, categoria, subcategoria, viralidad):
    if not gemini_model:
        return {
            "video_prompt": f"Video educativo sobre {categoria}: {titulo[:100]}",
            "duration": 20,
            "aspect_ratio": "9:16",
            "style": "educational",
            "text_overlay": f"Aprende sobre {categoria}"
        }

    prompt = f"""
    Genera un prompt detallado para crear un video educativo con Higgsfield.

    TEMA: {titulo}
    CATEGORIA: {categoria}
    SUBCATEGORIA: {subcategoria}
    VIRALIDAD POTENCIAL: {viralidad}/10
    CONTENIDO: {resumen[:800]}

    Responde SOLO con JSON:
    {{
        "video_prompt": "descripcion detallada",
        "duration": 20,
        "aspect_ratio": "9:16",
        "style": "educational",
        "text_overlay": "frase llamativa",
        "hashtags": ["#tag1", "#tag2"]
    }}
    """

    try:
        respuesta = gemini_model.generate_content(prompt)
        texto = respuesta.text
        if "```json" in texto:
            texto = texto.split("```json")[1].split("```")[0]
        return json.loads(texto)
    except:
        return {
            "video_prompt": f"Video educativo sobre {categoria}: {titulo[:100]}",
            "duration": 20,
            "aspect_ratio": "9:16",
            "style": "educational",
            "text_overlay": f"Aprende sobre {categoria}"
        }


def generar_video_con_higgsfield(prompt_data, titulo, categoria):
    """Genera un video usando la API de Higgsfield"""
    if not HIGGSFIELD_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {HIGGSFIELD_API_KEY}",
        "Content-Type": "application/json"
    }

    # Preparar el payload para Higgsfield
    payload = {
        "prompt": prompt_data.get("video_prompt", ""),
        "duration": prompt_data.get("duration", 15),
        "aspect_ratio": prompt_data.get("aspect_ratio", "9:16"),
        "style": prompt_data.get("style", "educational")
    }

    try:
        print("   🎬 Generando video con Higgsfield...")
        response = requests.post(HIGGSFIELD_API_URL, headers=headers, json=payload, timeout=60)

        if response.status_code == 200:
            result = response.json()
            video_url = result.get("video_url") or result.get("url")

            # Guardar información del video
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
            video_info = {
                "titulo": titulo,
                "categoria": categoria,
                "url": video_url,
                "created_at": datetime.now().isoformat()
            }

            info_path = os.path.join(VIDEOS_DIR, f"{timestamp}_{nombre_limpio}.json")
            with open(info_path, 'w', encoding='utf-8') as f:
                json.dump(video_info, f, ensure_ascii=False, indent=2)

            return video_url
        else:
            print(f"   ❌ Error Higgsfield: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"   ❌ Error generando video: {e}")
        return None


def guardar_resumen_notebooklm(titulo, categoria, subcategoria, resumen, url):
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

---
📌 Para Notebook LM: Copia este texto y pégalo como fuente.
"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(contenido)

    return filepath


def guardar_prompt_higgsfield(titulo, categoria, subcategoria, prompt_data, url):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
    filename = f"{timestamp}_{nombre_limpio}.json"
    filepath = os.path.join(HIGGSFIELD_DIR, filename)

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


def guardar_en_db(url, titulo, dominio, categoria, subcategoria, viralidad, resumen, archivo_resumen, archivo_higgsfield, video_url, motor_ia):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO contenido (
            fecha, url, titulo, dominio, categoria, subcategoria, viralidad, 
            resumen, archivo_resumen, archivo_higgsfield, video_url, motor_ia, procesado
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        video_url,
        motor_ia,
        1
    ))
    conn.commit()
    conn.close()


def procesar_enlace_completo(url, generar_video=False):
    print(f"\n📡 Procesando: {url[:80]}...")

    contenido = leer_contenido_url(url)
    if not contenido['exito']:
        return {"error": "No se pudo acceder", "url": url}

    print(f"   📄 Título: {contenido['titulo'][:60]}...")
    print(f"   🔗 Dominio: {contenido['dominio']}")
    print(f"   🐦 Es X/Twitter: {contenido['es_x_twitter']}")

    clasificacion = clasificar_contenido(
        contenido['titulo'],
        contenido['descripcion'],
        contenido['dominio'],
        contenido['es_x_twitter']
    )

    categoria = clasificacion['categoria']
    subcategoria = clasificacion['subcategoria']
    viralidad = clasificacion['viralidad']

    motor_usado = "manual"
    if contenido['es_x_twitter'] and GROK_API_KEY:
        motor_usado = "grok"
    elif gemini_model:
        motor_usado = "gemini"

    print(f"   📁 Categoría: {categoria} > {subcategoria} (motor: {motor_usado})")

    resumen = generar_resumen_notebooklm(
        contenido['titulo'],
        contenido['descripcion'],
        contenido['dominio'],
        categoria,
        subcategoria
    )

    prompt_higgsfield = generar_prompt_higgsfield(
        contenido['titulo'],
        resumen,
        categoria,
        subcategoria,
        viralidad
    )

    archivo_resumen = guardar_resumen_notebooklm(
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
        prompt_higgsfield,
        url
    )

    video_url = None
    if generar_video and HIGGSFIELD_API_KEY:
        video_url = generar_video_con_higgsfield(prompt_higgsfield, contenido['titulo'], categoria)

    guardar_en_db(
        url,
        contenido['titulo'],
        contenido['dominio'],
        categoria,
        subcategoria,
        viralidad,
        resumen,
        archivo_resumen,
        archivo_higgsfield,
        video_url,
        motor_usado
    )

    resultado = {
        "exito": True,
        "url": url,
        "titulo": contenido['titulo'],
        "categoria": categoria,
        "subcategoria": subcategoria,
        "viralidad": viralidad,
        "archivo_resumen": archivo_resumen,
        "archivo_higgsfield": archivo_higgsfield,
        "motor_usado": motor_usado
    }

    if video_url:
        resultado["video_url"] = video_url

    return resultado


# ============================================
# ENDPOINTS
# ============================================

@app.route('/')
def home():
    return jsonify({
        "servicio": "Construex Ecosystem",
        "estado": "activo",
        "version": "6.0.0",
        "motores_ia": {
            "gemini": bool(gemini_model),
            "grok": bool(GROK_API_KEY),
            "higgsfield": bool(HIGGSFIELD_API_KEY)
        },
        "funcionalidades": [
            "Clasificación híbrida (Gemini + Grok)",
            "Generación de resúmenes para Notebook LM",
            "Generación de prompts para Higgsfield",
            "Generación automática de videos (Higgsfield)"
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
    generar_video = data.get('generar_video', False)

    if not mensaje:
        return jsonify({"error": "No hay mensaje"}), 400

    enlaces = extraer_enlaces(mensaje)
    if not enlaces:
        return jsonify({"error": "No se encontraron enlaces"}), 400

    resultado = procesar_enlace_completo(enlaces[0], generar_video)
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


@app.route('/videos', methods=['GET'])
def listar_videos():
    archivos = os.listdir(VIDEOS_DIR) if os.path.exists(VIDEOS_DIR) else []
    videos_info = []
    for archivo in archivos:
        if archivo.endswith('.json'):
            with open(os.path.join(VIDEOS_DIR, archivo), 'r') as f:
                videos_info.append(json.load(f))
    return jsonify({"videos": videos_info[-20:]})


@app.route('/estadisticas', methods=['GET'])
def estadisticas():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM contenido")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT categoria, COUNT(*) FROM contenido GROUP BY categoria")
    stats = dict(cursor.fetchall())
    cursor.execute("SELECT motor_ia, COUNT(*) FROM contenido GROUP BY motor_ia")
    motores = dict(cursor.fetchall())
    cursor.execute("SELECT COUNT(*) FROM contenido WHERE video_url IS NOT NULL")
    videos_generados = cursor.fetchone()[0]
    conn.close()
    return jsonify({
        "total": total,
        "por_categoria": stats,
        "por_motor": motores,
        "videos_generados": videos_generados
    })


@app.route('/test', methods=['GET'])
def test():
    return jsonify({
        "status": "ok",
        "gemini_configured": bool(gemini_model),
        "grok_configured": bool(GROK_API_KEY),
        "higgsfield_configured": bool(HIGGSFIELD_API_KEY)
    })


# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    init_db()
    print("""
======================================================================
      CONSTRUEX ECOSYSTEM - COMPLETO (Gemini + Grok + Higgsfield)
======================================================================

MOTORES IA:
   Gemini: {}
   Grok: {}
   Higgsfield: {}

ESTRUCTURA GENERADA:
   📁 contenido/ (resúmenes para Notebook LM)
   📁 higgsfield_prompts/ (prompts para videos)
   📁 videos_generados/ (información de videos creados)

======================================================================
""".format(
        "Configurado" if gemini_model else "No configurado",
        "Configurado" if GROK_API_KEY else "No configurado",
        "Configurado" if HIGGSFIELD_API_KEY else "No configurado"
    ))
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)