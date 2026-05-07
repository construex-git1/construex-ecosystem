"""
======================================================================
                    CONSTRUEX ECOSYSTEM - VERSIÓN RENDER
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

DB_FILE = os.path.join(BASE_DIR, "construex.db")
url_cache = {}

# ============================================
# BASE DE DATOS
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
            archivo TEXT
        )
    ''')
    conn.commit()
    conn.close()

# ============================================
# FUNCIONES
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

def guardar_resumen(titulo, categoria, subcategoria, resumen, url):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
    filename = f"{timestamp}_{nombre_limpio}.txt"
    
    carpeta_base = CATEGORIAS_DIR.get(categoria, CATEGORIAS_DIR["Automejora"])
    carpeta_sub = os.path.join(carpeta_base, subcategoria)
    os.makedirs(carpeta_sub, exist_ok=True)
    filepath = os.path.join(carpeta_sub, filename)
    
    contenido = f"""CONTENIDO PARA NOTEBOOK LM
Fuente: {url}
Fecha: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Categoria: {categoria}
Subcategoria: {subcategoria}

{resumen}
"""
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(contenido)
    
    return filepath

def procesar_enlace_completo(url):
    contenido = leer_contenido_url(url)
    if not contenido['exito']:
        return {"error": "No se pudo acceder", "url": url}
    
    clasificacion = clasificar_con_ia(
        contenido['titulo'],
        contenido['descripcion'],
        contenido['dominio']
    )
    
    categoria = clasificacion['categoria']
    subcategoria = clasificacion['subcategoria']
    viralidad = clasificacion['viralidad']
    
    resumen = f"Resumen: {contenido['descripcion'][:500]}"
    
    archivo = guardar_resumen(
        contenido['titulo'],
        categoria,
        subcategoria,
        resumen,
        url
    )
    
    return {
        "exito": True,
        "url": url,
        "titulo": contenido['titulo'],
        "categoria": categoria,
        "subcategoria": subcategoria,
        "viralidad": viralidad,
        "archivo": archivo
    }

# ============================================
# ENDPOINTS
# ============================================

@app.route('/')
def home():
    return jsonify({
        "servicio": "Construex Ecosystem",
        "estado": "activo",
        "version": "1.0.0"
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

# ============================================
# MAIN - CORREGIDO PARA RENDER
# ============================================

if __name__ == '__main__':
    init_db()
    print("""
======================================================================
         CONSTRUEX ECOSYSTEM - CORRIENDO
======================================================================
""")
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)