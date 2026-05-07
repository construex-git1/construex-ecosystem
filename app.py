"""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN FINAL COMPLETA
======================================================================
"""

import os
import re
import json
import requests
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
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

# Gemini API (principal)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    gemini_model = None

# Grok API (para X/Twitter)
GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

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
            motor_ia TEXT,
            procesado BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada")


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
    motor_usado = "manual"

    if es_x_twitter and GROK_API_KEY:
        print("   🔍 Usando Grok (X/Twitter)...")
        resultado = clasificar_con_grok(titulo, descripcion, dominio)
        if resultado:
            motor_usado = "grok"

    if not resultado and gemini_model:
        print("   🔍 Usando Gemini...")
        resultado = clasificar_con_gemini(titulo, descripcion, dominio)
        if resultado:
            motor_usado = "gemini"

    if not resultado:
        print("   ⚠️ Fallback a clasificación manual")
        texto = f"{titulo} {descripcion}".lower()
        if any(p in texto for p in ["construc", "arquitect", "obra", "cemento", "archdaily"]):
            resultado = {"categoria": "Construccion", "subcategoria": "General", "viralidad": 7}
        elif any(p in texto for p in ["negocio", "emprend", "empresa", "ventas"]):
            resultado = {"categoria": "Emprendimiento", "subcategoria": "General", "viralidad": 7}
        elif any(p in texto for p in ["curso", "aprender", "educacion"]):
            resultado = {"categoria": "Construex University", "subcategoria": "General", "viralidad": 6}
        elif any(p in texto for p in ["salud", "medico", "bienestar"]):
            resultado = {"categoria": "Salud", "subcategoria": "General", "viralidad": 6}
        else:
            resultado = {"categoria": "Automejora", "subcategoria": "General", "viralidad": 5}
        motor_usado = "fallback"

    resultado['motor'] = motor_usado
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
            "style": "educational"
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
            "style": "educational"
        }


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


def guardar_en_db(url, titulo, dominio, categoria, subcategoria, viralidad, resumen, archivo_resumen, archivo_higgsfield, motor_ia):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO contenido (
            fecha, url, titulo, dominio, categoria, subcategoria, viralidad,
            resumen, archivo_resumen, archivo_higgsfield, motor_ia, procesado
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        motor_ia,
        1
    ))
    conn.commit()
    conn.close()


def procesar_enlace_completo(url):
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
    motor_usado = clasificacion.get('motor', 'manual')

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
        motor_usado
    )

    return {
        "exito": True,
        "url": url,
        "titulo": contenido['titulo'],
        "categoria": categoria,
        "subcategoria": subcategoria,
        "viralidad": viralidad,
        "motor_usado": motor_usado,
        "archivo_resumen": archivo_resumen,
        "archivo_higgsfield": archivo_higgsfield,
        "resumen": resumen
    }


# ============================================
# DASHBOARD VISUAL (INTERFAZ WEB)
# ============================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Construex Ecosystem - Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #2c3e50; margin-bottom: 10px; }
        .subtitle { color: #7f8c8d; margin-bottom: 30px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }
        .stat-number { font-size: 36px; font-weight: bold; color: #3498db; }
        .stat-label { color: #7f8c8d; margin-top: 5px; }
        .content-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }
        .card { background: white; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow: hidden; }
        .card-header { background: #3498db; color: white; padding: 15px 20px; font-weight: bold; }
        .card-body { padding: 20px; max-height: 400px; overflow-y: auto; }
        .card-body ul { list-style: none; }
        .card-body li { padding: 10px 0; border-bottom: 1px solid #eee; }
        .card-body li:last-child { border-bottom: none; }
        .categoria-badge { display: inline-block; padding: 2px 8px; border-radius: 15px; font-size: 11px; font-weight: bold; margin-right: 10px; }
        .Salud { background: #4CAF50; color: white; }
        .Emprendimiento { background: #FF9800; color: white; }
        .Automejora { background: #9C27B0; color: white; }
        .Construccion { background: #795548; color: white; }
        .Construex-University { background: #2196F3; color: white; }
        .motor { font-size: 11px; color: #999; margin-left: 10px; }
        .url { font-size: 12px; color: #666; word-break: break-all; }
        .fecha { font-size: 11px; color: #999; }
        .resumen-preview { font-size: 12px; color: #555; margin-top: 5px; }
        .procesar-form { background: white; border-radius: 10px; padding: 20px; margin-bottom: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .procesar-form input { width: 70%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; margin-right: 10px; }
        .procesar-form button { padding: 12px 24px; background: #3498db; color: white; border: none; border-radius: 5px; cursor: pointer; }
        .procesar-form button:hover { background: #2980b9; }
        .resultado { margin-top: 15px; padding: 15px; background: #e8f4f8; border-radius: 5px; display: none; }
        .refresh-btn { background: #2ecc71; margin-left: 10px; }
        .refresh-btn:hover { background: #27ae60; }
        @media (max-width: 768px) { .content-grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏗️ Construex Ecosystem</h1>
        <div class="subtitle">Sistema de clasificación de contenido con IA</div>
        
        <div class="procesar-form">
            <h3>Procesar nuevo enlace</h3>
            <input type="text" id="urlInput" placeholder="https://ejemplo.com/articulo" style="width: 80%;">
            <button onclick="procesarUrl()">Procesar</button>
            <button class="refresh-btn" onclick="cargarDatos()">Actualizar Dashboard</button>
            <div id="resultadoProcesamiento" class="resultado"></div>
        </div>
        
        <div class="stats-grid" id="stats">
            <div class="stat-card"><div class="stat-number">-</div><div class="stat-label">Total analizados</div></div>
            <div class="stat-card"><div class="stat-number">-</div><div class="stat-label">Viralidad promedio</div></div>
            <div class="stat-card"><div class="stat-number">-</div><div class="stat-label">Categorías</div></div>
            <div class="stat-card"><div class="stat-number">-</div><div class="stat-label">Enlaces procesados</div></div>
        </div>
        
        <div class="content-grid">
            <div class="card">
                <div class="card-header">📁 Últimos contenidos analizados</div>
                <div class="card-body" id="ultimosContenidos">Cargando...</div>
            </div>
            <div class="card">
                <div class="card-header">📊 Distribución por categoría</div>
                <div class="card-body" id="distribucion">Cargando...</div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">🎬 Prompts generados para Higgsfield</div>
            <div class="card-body" id="higgsfieldPrompts">Cargando...</div>
        </div>
    </div>
    
    <script>
        async function cargarDatos() {
            await cargarEstadisticas();
            await cargarUltimos();
            await cargarDistribucion();
            await cargarHiggsfield();
        }
        
        async function cargarEstadisticas() {
            const response = await fetch('/estadisticas');
            const data = await response.json();
            document.getElementById('stats').innerHTML = `
                <div class="stat-card"><div class="stat-number">${data.total || 0}</div><div class="stat-label">Total analizados</div></div>
                <div class="stat-card"><div class="stat-number">${data.viral_promedio || 0}/10</div><div class="stat-label">Viralidad promedio</div></div>
                <div class="stat-card"><div class="stat-number">${Object.keys(data.por_categoria || {}).length}</div><div class="stat-label">Categorías</div></div>
                <div class="stat-card"><div class="stat-number">${data.total || 0}</div><div class="stat-label">Enlaces procesados</div></div>
            `;
        }
        
        async function cargarUltimos() {
            const response = await fetch('/ultimos');
            const data = await response.json();
            if (data.ultimos && data.ultimos.length > 0) {
                let html = '<ul>';
                for (let item of data.ultimos) {
                    html += `<li>
                        <span class="categoria-badge ${item.categoria.replace(/ /g, '-')}">${item.categoria}</span>
                        <strong>${item.titulo ? item.titulo.substring(0, 80) : 'Sin titulo'}</strong>
                        <div class="url">${item.url ? item.url.substring(0, 80) : ''}...</div>
                        <div class="fecha">${item.fecha ? item.fecha.substring(0, 19) : ''} | Motor: ${item.motor_ia || 'manual'}</div>
                        <div class="resumen-preview">${item.resumen ? item.resumen.substring(0, 100) + '...' : ''}</div>
                    </li>`;
                }
                html += '</ul>';
                document.getElementById('ultimosContenidos').innerHTML = html;
            } else {
                document.getElementById('ultimosContenidos').innerHTML = '<p>No hay contenido procesado aún</p>';
            }
        }
        
        async function cargarDistribucion() {
            const response = await fetch('/estadisticas');
            const data = await response.json();
            if (data.por_categoria && Object.keys(data.por_categoria).length > 0) {
                let html = '<ul>';
                for (let [cat, count] of Object.entries(data.por_categoria)) {
                    html += `<li><span class="categoria-badge ${cat.replace(/ /g, '-')}">${cat}</span> ${count} contenidos</li>`;
                }
                html += '</ul>';
                document.getElementById('distribucion').innerHTML = html;
            } else {
                document.getElementById('distribucion').innerHTML = '<p>No hay datos de distribución</p>';
            }
        }
        
        async function cargarHiggsfield() {
            const response = await fetch('/higgsfield');
            const data = await response.json();
            if (data.prompts_higgsfield && data.prompts_higgsfield.length > 0) {
                let html = '<ul>';
                for (let item of data.prompts_higgsfield) {
                    html += `<li><strong>${item}</strong><br><small>Prompt listo para copiar a Higgsfield</small></li>`;
                }
                html += '</ul>';
                document.getElementById('higgsfieldPrompts').innerHTML = html;
            } else {
                document.getElementById('higgsfieldPrompts').innerHTML = '<p>No hay prompts generados aún</p>';
            }
        }
        
        async function procesarUrl() {
            const url = document.getElementById('urlInput').value;
            if (!url) {
                alert('Ingresa una URL');
                return;
            }
            
            const resultadoDiv = document.getElementById('resultadoProcesamiento');
            resultadoDiv.style.display = 'block';
            resultadoDiv.innerHTML = '<p>Procesando enlace...</p>';
            
            try {
                const response = await fetch('/procesar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mensaje: url })
                });
                const data = await response.json();
                
                if (data.exito) {
                    resultadoDiv.innerHTML = `
                        <strong>✅ Procesado correctamente</strong><br>
                        📁 Categoría: ${data.categoria}<br>
                        📂 Subcategoría: ${data.subcategoria}<br>
                        🔥 Viralidad: ${data.viralidad}/10<br>
                        🤖 Motor usado: ${data.motor_usado || 'IA'}<br>
                        📄 Resumen: ${data.resumen ? data.resumen.substring(0, 200) + '...' : 'No disponible'}<br>
                        📁 Archivo resumen: ${data.archivo_resumen ? data.archivo_resumen.split('/').pop() : 'N/A'}<br>
                        🎬 Archivo Higgsfield: ${data.archivo_higgsfield ? data.archivo_higgsfield.split('/').pop() : 'N/A'}
                    `;
                    cargarDatos();
                    document.getElementById('urlInput').value = '';
                } else {
                    resultadoDiv.innerHTML = `<strong>❌ Error:</strong> ${data.error || 'No se pudo procesar'}`;
                }
            } catch (error) {
                resultadoDiv.innerHTML = `<strong>❌ Error:</strong> ${error.message}`;
            }
        }
        
        cargarDatos();
        setInterval(cargarDatos, 30000);
    </script>
</body>
</html>
"""


# ============================================
# ENDPOINTS
# ============================================

@app.route('/')
def home():
    return DASHBOARD_HTML


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
                        procesar_enlace_completo(enlace)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Error webhook: {e}")
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
            contenido_cat = {}
            for sub in os.listdir(path):
                sub_path = os.path.join(path, sub)
                if os.path.isdir(sub_path):
                    contenido_cat[sub] = os.listdir(sub_path) if os.listdir(sub_path) else []
                else:
                    contenido_cat[sub] = "Archivo"
            estructura[cat] = contenido_cat
    return jsonify({"estructura": estructura}), 200


@app.route('/higgsfield', methods=['GET'])
def listar_higgsfield():
    archivos = os.listdir(HIGGSFIELD_DIR) if os.path.exists(HIGGSFIELD_DIR) else []
    return jsonify({"prompts_higgsfield": archivos[-20:]}), 200


@app.route('/ultimos', methods=['GET'])
def ultimos_contenidos():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT fecha, url, titulo, categoria, subcategoria, viralidad, resumen, motor_ia
        FROM contenido
        ORDER BY id DESC
        LIMIT 20
    ''')
    ultimos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"ultimos": ultimos}), 200


@app.route('/estadisticas', methods=['GET'])
def estadisticas():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM contenido")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT categoria, COUNT(*) FROM contenido GROUP BY categoria")
    por_categoria = dict(cursor.fetchall())
    cursor.execute("SELECT AVG(viralidad) FROM contenido")
    viral_promedio = cursor.fetchone()[0] or 0
    conn.close()
    return jsonify({
        "total": total,
        "por_categoria": por_categoria,
        "viral_promedio": round(viral_promedio, 1)
    }), 200


@app.route('/test', methods=['GET'])
def test():
    return jsonify({
        "status": "ok",
        "gemini_configured": bool(gemini_model),
        "grok_configured": bool(GROK_API_KEY),
        "message": "Sistema Construex funcionando correctamente"
    }), 200


# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    init_db()
    print("""
======================================================================
      CONSTRUEX ECOSYSTEM - VERSIÓN FINAL COMPLETA
======================================================================

MOTORES IA:
   Gemini: {}
   Grok: {}

DASHBOARD VISUAL: http://localhost:10000/
WEBHOOK: /webhook
PROCESAR: POST /procesar

======================================================================
""".format("Configurado" if gemini_model else "No configurado",
           "Configurado" if GROK_API_KEY else "No configurado"))
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)