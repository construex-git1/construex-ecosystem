"""
======================================================================
                    CONSTRUEX ECOSYSTEM - AUTOMATIZACIÓN COMPLETA
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
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# ============================================
# CONFIGURACION
# ============================================

WHATSAPP_VERIFY_TOKEN = "construex_verify_2026"
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "1056445960894111")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configurar Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    gemini_model = None
    print("⚠️ GEMINI_API_KEY no configurada")

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

# Crear carpeta para prompts de Higgsfield
HIGGSFIELD_DIR = os.path.join(BASE_DIR, "higgsfield_prompts")
os.makedirs(HIGGSFIELD_DIR, exist_ok=True)

DB_FILE = os.path.join(BASE_DIR, "construex.db")
url_cache = {}

# ============================================
# BASE DE DATOS MEJORADA
# ============================================

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
            publicado BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada")

# ============================================
# FUNCIONES DE GENERACIÓN
# ============================================

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

def clasificar_con_ia(titulo, descripcion, dominio):
    if not gemini_model:
        return {"categoria": "Automejora", "subcategoria": "General", "viralidad": 5}
    
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
    except:
        return {"categoria": "Automejora", "subcategoria": "General", "viralidad": 5}

# ============================================
# FUNCIÓN 1: Resumen para Notebook LM
# ============================================

def generar_resumen_notebooklm(titulo, descripcion, dominio, categoria, subcategoria):
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

# ============================================
# FUNCIÓN 2: Prompt para Higgsfield (videos)
# ============================================

def generar_prompt_higgsfield(titulo, resumen, categoria, subcategoria, viralidad):
    prompt = f"""
    Genera un prompt detallado para crear un video educativo con Higgsfield.

    INFORMACION DEL CONTENIDO:
    TEMA: {titulo}
    CATEGORIA: {categoria}
    SUBCATEGORIA: {subcategoria}
    VIRALIDAD POTENCIAL: {viralidad}/10
    CONTENIDO: {resumen[:800]}

    FORMATO DE RESPUESTA (JSON):
    {{
        "video_prompt": "descripcion detallada para generar el video",
        "duracion": 20,
        "aspect_ratio": "9:16",
        "estilo": "educativo",
        "texto_overlay": "frase llamativa",
        "recomendaciones": ["recomendacion1", "recomendacion2"],
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
            "duracion": 20,
            "aspect_ratio": "9:16",
            "estilo": "educativo",
            "texto_overlay": f"Aprende sobre {subcategoria}",
            "recomendaciones": ["Usar ejemplos visuales", "Incluir datos clave"],
            "hashtags": [f"#{categoria.replace(' ', '')}", "#educacion", "#aprende"]
        }

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

# ============================================
# FUNCIÓN 3: Procesamiento completo
# ============================================

def procesar_enlace_completo(url):
    """Procesa un enlace y genera TODO: resumen + prompt para Higgsfield"""
    
    print(f"📡 Procesando: {url[:80]}...")
    
    # 1. Extraer contenido
    contenido = leer_contenido_url(url)
    if not contenido['exito']:
        return {"error": "No se pudo acceder", "url": url}
    
    # 2. Clasificar
    clasificacion = clasificar_con_ia(
        contenido['titulo'],
        contenido['descripcion'],
        contenido['dominio']
    )
    
    categoria = clasificacion['categoria']
    subcategoria = clasificacion['subcategoria']
    viralidad = clasificacion['viralidad']
    
    print(f"   📁 {categoria} > {subcategoria}")
    
    # 3. Generar resumen para Notebook LM
    resumen = generar_resumen_notebooklm(
        contenido['titulo'],
        contenido['descripcion'],
        contenido['dominio'],
        categoria,
        subcategoria
    )
    
    # 4. Guardar resumen
    archivo_resumen = guardar_resumen_notebooklm(
        contenido['titulo'],
        categoria,
        subcategoria,
        resumen,
        url
    )
    
    # 5. Generar prompt para Higgsfield
    prompt_higgsfield = generar_prompt_higgsfield(
        contenido['titulo'],
        resumen,
        categoria,
        subcategoria,
        viralidad
    )
    
    # 6. Guardar prompt de Higgsfield
    archivo_higgsfield = guardar_prompt_higgsfield(
        contenido['titulo'],
        categoria,
        subcategoria,
        prompt_higgsfield,
        url
    )
    
    # 7. Guardar en BD
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO contenido (fecha, url, titulo, dominio, categoria, subcategoria, viralidad, resumen, archivo_resumen, prompt_higgsfield, archivo_higgsfield)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().isoformat(),
        url,
        contenido['titulo'][:200],
        contenido['dominio'],
        categoria,
        subcategoria,
        viralidad,
        resumen[:500],
        archivo_resumen,
        json.dumps(prompt_higgsfield),
        archivo_higgsfield
    ))
    conn.commit()
    conn.close()
    
    return {
        "exito": True,
        "url": url,
        "titulo": contenido['titulo'],
        "categoria": categoria,
        "subcategoria": subcategoria,
        "viralidad": viralidad,
        "archivo_resumen": archivo_resumen,
        "archivo_higgsfield": archivo_higgsfield,
        "prompt_higgsfield": prompt_higgsfield
    }

# ============================================
# ENDPOINTS
# ============================================

@app.route('/')
def home():
    return jsonify({
        "servicio": "Construex Ecosystem",
        "estado": "activo",
        "version": "3.0.0",
        "funcionalidades": [
            "Clasificacion de enlaces",
            "Generacion de resumenes para Notebook LM",
            "Generacion de prompts para Higgsfield (videos)",
            "Publicacion automatica (proximamente)"
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

# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    init_db()
    print("""
======================================================================
         CONSTRUEX ECOSYSTEM - AUTOMATIZACIÓN COMPLETA
======================================================================

ESTRUCTURA GENERADA:
   📁 contenido/
      📁 Salud/
      📁 Emprendimiento/
      📁 Automejora/
      📁 Construccion/
      📁 Construex_University/
   📁 higgsfield_prompts/

FUNCIONALIDADES ACTIVAS:
   ✅ Procesar enlaces: POST /procesar
   ✅ Generar resumen para Notebook LM
   ✅ Generar prompt para Higgsfield (videos)
   ✅ Almacenar en estructura organizada
   ✅ Ver estructura: GET /estructura
   ✅ Ver prompts: GET /higgsfield
   ✅ Estadisticas: GET /estadisticas

======================================================================
""")
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)