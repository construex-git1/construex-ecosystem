"""
======================================================================
                    CONSTRUEX ECOSYSTEM - VERSIÓN PROFESIONAL
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
import threading

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
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

# Directorios organizados por categoria
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATEGORIAS_DIR = {
    "Salud": os.path.join(BASE_DIR, "contenido", "Salud"),
    "Emprendimiento": os.path.join(BASE_DIR, "contenido", "Emprendimiento"),
    "Automejora": os.path.join(BASE_DIR, "contenido", "Automejora"),
    "Construccion": os.path.join(BASE_DIR, "contenido", "Construccion"),
    "Construex University": os.path.join(BASE_DIR, "contenido", "Construex_University")
}

# Crear carpetas
for carpeta in CATEGORIAS_DIR.values():
    os.makedirs(carpeta, exist_ok=True)

# Subcarpetas para cada categoria
SUBCARPETAS = {
    "Salud": ["Nutricion", "Ejercicio", "Salud_Mental", "Prevencion", "Bienestar"],
    "Emprendimiento": ["Negocios", "Marketing", "Ventas", "Finanzas", "Liderazgo"],
    "Automejora": ["Productividad", "Habitos", "Motivacion", "Disciplina", "Crecimiento"],
    "Construccion": ["Materiales", "Tecnicas", "Proyectos", "Normativas", "Seguridad"],
    "Construex University": ["Cursos", "Certificaciones", "Talleres", "Webinars", "Diplomados"]
}

# Crear subcarpetas
for cat, subcats in SUBCARPETAS.items():
    cat_path = CATEGORIAS_DIR[cat]
    for subcat in subcats:
        os.makedirs(os.path.join(cat_path, subcat), exist_ok=True)

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
            confianza REAL,
            razon TEXT,
            sugerencia TEXT,
            resumen TEXT,
            archivo TEXT,
            procesado_para_higgsfield INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

# ============================================
# FUNCIONES DE CLASIFICACION PRECISA CON IA
# ============================================

def clasificar_con_ia(titulo, descripcion, dominio):
    """
    Clasifica el contenido usando Gemini IA para mayor precision
    Retorna: categoria, subcategoria, viralidad, confianza, razon, sugerencia
    """
    
    prompt = f"""
    Eres un clasificador experto. Analiza el siguiente contenido y clasificalo en UNA de estas categorias:

    CATEGORIAS DISPONIBLES:
    1. Salud: Temas relacionados con salud fisica, mental, nutricion, ejercicio, bienestar
    2. Emprendimiento: Negocios, ventas, marketing, finanzas, liderazgo empresarial
    3. Automejora: Productividad, habitos, motivacion, desarrollo personal, disciplina
    4. Construccion: Arquitectura, obras, materiales, tecnicas de construccion, proyectos
    5. Construex University: Educacion, cursos, capacitacion, certificaciones, talleres

    SUBCATEGORIAS POR CATEGORIA:
    - Salud: Nutricion, Ejercicio, Salud_Mental, Prevencion, Bienestar
    - Emprendimiento: Negocios, Marketing, Ventas, Finanzas, Liderazgo
    - Automejora: Productividad, Habitos, Motivacion, Disciplina, Crecimiento
    - Construccion: Materiales, Tecnicas, Proyectos, Normativas, Seguridad
    - Construex University: Cursos, Certificaciones, Talleres, Webinars, Diplomas

    CONTENIDO A ANALIZAR:
    Titulo: {titulo}
    Dominio: {dominio}
    Descripcion: {descripcion[:1000]}

    Responde SOLO con JSON en este formato:
    {{
        "categoria": "nombre_de_la_categoria",
        "subcategoria": "nombre_de_la_subcategoria",
        "viralidad": 7,
        "confianza": 0.95,
        "razon": "breve explicacion de por que esta categoria",
        "sugerencia": "video/podcast/infografia/hilo_twitter/curso"
    }}
    """
    
    try:
        respuesta = gemini_model.generate_content(prompt)
        texto = respuesta.text
        if "```json" in texto:
            texto = texto.split("```json")[1].split("```")[0]
        resultado = json.loads(texto.strip())
        return resultado
    except Exception as e:
        print(f"Error en clasificacion IA: {e}")
        return {
            "categoria": "Automejora",
            "subcategoria": "Crecimiento",
            "viralidad": 5,
            "confianza": 0.5,
            "razon": "Error en IA, usando fallback",
            "sugerencia": "articulo_blog"
        }

# ============================================
# FUNCION DE RESUMEN DE ÉLITE PARA NOTEBOOK LM
# ============================================

def generar_resumen_notebooklm(titulo, descripcion, dominio, categoria, subcategoria):
    """
    Genera un resumen de altísima calidad, optimizado para Notebook LM
    """
    prompt = f"""
    Actúa como el Director de Conocimiento de Construex University.
    Crea un Módulo de Aprendizaje Construex para nuestra base de conocimiento.

    ---
    TITULO: {titulo}
    CATEGORIA: {categoria}
    SUBCATEGORIA: {subcategoria}
    FUENTE: {dominio}
    CONTENIDO: {descripcion[:2000]}
    ---

    GENERA EL MÓDULO CON ESTA ESTRUCTURA EXACTA:

    ## 📚 MÓDULO DE APRENDIZAJE CONSTRUEX

    **Tema Central:** [Frase corta que resuma la esencia]

    ### 1. Resumen Estratégico
    [2-3 párrafos explicando el contexto, la solución y por qué es crucial]

    ### 2. Ideas Clave
    *   **Idea 1:** [Primera idea fundamental]
    *   **Idea 2:** [Segunda idea fundamental]
    *   **Idea 3:** [Tercera idea fundamental]

    ### 3. Para Notebook LM (Formato Q&A)
    > **Pregunta Clave 1:** [Pregunta importante]
    > **Respuesta:** [Respuesta basada en el artículo]

    > **Pregunta Clave 2:** [Segunda pregunta importante]
    > **Respuesta:** [Respuesta basada en el artículo]

    ### 4. Conclusión Construex
    [1-2 frases invitando a la acción, mencionando cursos relacionados de {subcategoria}]
    """
    
    try:
        respuesta = gemini_model.generate_content(prompt)
        return respuesta.text
    except Exception as e:
        print(f"Error generando resumen: {e}")
        return f"**Error:** No se pudo generar el módulo para '{titulo}'."

# ============================================
# FUNCIONES DE EXTRACCION DE CONTENIDO
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

def guardar_resumen(titulo, categoria, subcategoria, resumen, url):
    """Guarda el resumen en la carpeta correspondiente"""
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

def guardar_en_db(url, titulo, dominio, categoria, subcategoria, viralidad, confianza, razon, sugerencia, resumen, archivo):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO contenido (fecha, url, titulo, dominio, categoria, subcategoria, viralidad, confianza, razon, sugerencia, resumen, archivo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (datetime.now().isoformat(), url, titulo[:200], dominio, categoria, subcategoria, viralidad, confianza, razon, sugerencia, resumen[:500], archivo))
    conn.commit()
    conn.close()

def procesar_enlace_completo(url):
    """Procesa un enlace completo: extrae, clasifica, guarda"""
    print(f"📡 Procesando: {url[:80]}...")
    
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
    confianza = clasificacion.get('confianza', 0.7)
    razon = clasificacion.get('razon', '')
    sugerencia = clasificacion.get('sugerencia', 'articulo_blog')
    
    print(f"   📁 {categoria} > {subcategoria} (confianza: {confianza:.0%})")
    
    resumen = generar_resumen_notebooklm(
        contenido['titulo'],
        contenido['descripcion'],
        contenido['dominio'],
        categoria,
        subcategoria
    )
    
    archivo = guardar_resumen(
        contenido['titulo'],
        categoria,
        subcategoria,
        resumen,
        url
    )
    
    guardar_en_db(
        url,
        contenido['titulo'],
        contenido['dominio'],
        categoria,
        subcategoria,
        viralidad,
        confianza,
        razon,
        sugerencia,
        resumen,
        archivo
    )
    
    return {
        "exito": True,
        "url": url,
        "titulo": contenido['titulo'],
        "categoria": categoria,
        "subcategoria": subcategoria,
        "viralidad": viralidad,
        "confianza": confianza,
        "archivo": archivo,
        "sugerencia": sugerencia
    }

# ============================================
# WEBHOOK Y ENDPOINTS
# ============================================

def enviar_whatsapp(to_number, text):
    if not WHATSAPP_ACCESS_TOKEN:
        return None
    url = f"https://graph.facebook.com/v25.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": to_number, "type": "text", "text": {"body": text[:1000]}}
    try:
        return requests.post(url, headers=headers, json=data, timeout=10).json()
    except:
        return None

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
    try:
        data = request.get_json()
        entry = data.get('entry', [])
        if not entry:
            return jsonify({"status": "ok"}), 200
        for change in entry[0].get('changes', []):
            value = change.get('value', {})
            messages = value.get('messages', [])
            for message in messages:
                from_number = message.get('from')
                if message.get('type') == 'text':
                    text = message.get('text', {}).get('body', '')
                    enlaces = extraer_enlaces(text)
                    for enlace in enlaces:
                        resultado = procesar_enlace_completo(enlace)
                        if resultado.get('exito'):
                            resp = f"✅ Analizado: {resultado['categoria']} > {resultado['subcategoria']}. Resumen guardado. Sugerencia: {resultado.get('sugerencia', 'leer mas')}"
                            enviar_whatsapp(from_number, resp)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error"}), 500

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

@app.route('/admin/dashboard', methods=['GET'])
def admin_dashboard():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM contenido")
    total_analizados = cursor.fetchone()[0]
    cursor.execute("SELECT categoria, COUNT(*) FROM contenido GROUP BY categoria")
    stats_cat = dict(cursor.fetchall())
    cursor.execute("SELECT fecha, url, categoria FROM contenido ORDER BY id DESC LIMIT 10")
    ultimos = cursor.fetchall()
    conn.close()

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Construex - Admin Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #2c3e50; }}
            .stats {{ background: #e8f4f8; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #3498db; color: white; }}
        </style>
    </head>
    <body>
        <h1>📊 Dashboard del Ecosistema Construex</h1>
        <div class="stats">
            <strong>Total de Contenido Analizado:</strong> {total_analizados}
        </div>
        <h2>📁 Estadísticas por Categoría</h2>
        <ul>
            {''.join([f'<li><strong>{cat}:</strong> {count}</li>' for cat, count in stats_cat.items()])}
        </ul>
        <h2>📋 Últimos 10 Análisis</h2>
        <table>
            <tr><th>Fecha</th><th>URL</th><th>Categoría</th></tr>
            {''.join([f'<tr><td>{fecha[:19]}</td><td><a href="{url}" target="_blank">{url[:50]}...</a></td><td>{cat}</td></tr>' for fecha, url, cat in ultimos])}
        </table>
    </body>
    </html>
    """
    return html

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "servicio": "Construex Ecosystem",
        "version": "2.0.0",
        "clasificacion": "IA precisa con confianza",
        "carpetas": list(CATEGORIAS_DIR.keys()),
        "endpoints": {
            "webhook": "/webhook",
            "procesar": "/procesar (POST)",
            "estructura": "/estructura",
            "admin": "/admin/dashboard"
        }
    })

# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    init_db()
    print("""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN PROFESIONAL
======================================================================

ESTRUCTURA DE CARPETAS GENERADA:
""")
    for cat, path in CATEGORIAS_DIR.items():
        print(f"   📁 {cat}")
        for subcat in SUBCARPETAS.get(cat, []):
            print(f"      📂 {subcat}")

    print("""
======================================================================
✅ Servidor corriendo...
✅ Dashboard admin: /admin/dashboard
✅ Resúmenes en formato Markdown (.md)
✅ Clasificación con nivel de confianza
======================================================================
""")
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)