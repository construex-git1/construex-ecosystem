"""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN CON VISUALIZACIÓN
======================================================================
"""

import os
import re
import json
import requests
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# ============================================
# CONFIGURACION
# ============================================

WHATSAPP_VERIFY_TOKEN = "construex_verify_2026"

# APIs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HIGGSFIELD_API_KEY = os.getenv("HIGGSFIELD_API_KEY", "72700186-4d90-427e-ab87-d01b13ea189b")
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
            archivo_resumen TEXT,
            archivo_higgsfield TEXT,
            video_url TEXT,
            motor_ia TEXT,
            procesado BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada")

# ============================================
# FUNCIONES DE EXTRACCION Y CLASIFICACION
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

def clasificar_manual(titulo, descripcion, dominio):
    texto = f"{titulo} {descripcion}".lower()
    if any(p in texto for p in ["construc", "canal", "obra", "cemento", "arquitect", "edificio"]):
        return "Construccion", "Proyectos", 8
    elif any(p in texto for p in ["negocio", "emprend", "empresa", "ventas", "inversion"]):
        return "Emprendimiento", "Negocios", 7
    elif any(p in texto for p in ["curso", "aprender", "educacion", "certificacion"]):
        return "Construex University", "Cursos", 6
    elif any(p in texto for p in ["salud", "medico", "bienestar", "dieta", "ejercicio"]):
        return "Salud", "Bienestar", 6
    return "Automejora", "Crecimiento", 5

# ============================================
# GENERACION DE CONTENIDO
# ============================================

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

def generar_prompt_higgsfield(titulo, resumen, categoria, subcategoria, viralidad):
    return {
        "video_prompt": f"Video educativo sobre {categoria}: {titulo[:100]}\n\nContenido: {resumen[:300]}",
        "duration": 20,
        "aspect_ratio": "9:16",
        "style": "educational",
        "text_overlay": f"Aprende sobre {categoria}",
        "hashtags": [f"#{categoria.replace(' ', '')}", "#Construex", "#Educacion"]
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

def guardar_en_db(url, titulo, dominio, categoria, subcategoria, viralidad, resumen, archivo_resumen, archivo_higgsfield, video_url, motor_ia):
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
            video_url TEXT,
            motor_ia TEXT,
            procesado BOOLEAN DEFAULT 0
        )
    ''')

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

    resultado = {
        "exito": True,
        "url": url,
        "error": None
    }

    try:
        contenido = leer_contenido_url(url)
        if not contenido['exito']:
            resultado['error'] = "No se pudo acceder al enlace"
            resultado['exito'] = False
            return resultado

        resultado['titulo'] = contenido['titulo']
        categoria, subcategoria, viralidad = clasificar_manual(
            contenido['titulo'],
            contenido['descripcion'],
            contenido['dominio']
        )

        resultado['categoria'] = categoria
        resultado['subcategoria'] = subcategoria
        resultado['viralidad'] = viralidad
        resultado['motor_usado'] = "manual"

        resumen = f"Resumen de '{contenido['titulo']}': {contenido['descripcion'][:500]}"
        resultado['resumen'] = resumen

        archivo_resumen = guardar_resumen(contenido['titulo'], categoria, subcategoria, resumen, url)
        resultado['archivo_resumen'] = archivo_resumen

        prompt_higgsfield = generar_prompt_higgsfield(contenido['titulo'], resumen, categoria, subcategoria, viralidad)
        archivo_higgsfield = guardar_prompt_higgsfield(contenido['titulo'], categoria, subcategoria, prompt_higgsfield, url)
        resultado['archivo_higgsfield'] = archivo_higgsfield
        resultado['prompt_higgsfield'] = prompt_higgsfield

        video_url = None
        if generar_video and HIGGSFIELD_API_KEY:
            video_url = "https://ejemplo.com/video_generado.mp4"  # Placeholder
            resultado['video_url'] = video_url

        guardar_en_db(url, contenido['titulo'], contenido['dominio'], categoria, subcategoria, viralidad, resumen, archivo_resumen, archivo_higgsfield, video_url, "manual")

        return resultado

    except Exception as e:
        print(f"   ❌ Error: {e}")
        resultado['exito'] = False
        resultado['error'] = str(e)
        return resultado

# ============================================
# DASHBOARD CON VISUALIZACIÓN
# ============================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Construex Ecosystem - Dashboard Visual</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #2c3e50; margin-bottom: 10px; }
        .subtitle { color: #7f8c8d; margin-bottom: 30px; }
        
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }
        .stat-number { font-size: 36px; font-weight: bold; color: #3498db; }
        .stat-label { color: #7f8c8d; margin-top: 5px; }
        
        .procesar-form { background: white; border-radius: 15px; padding: 25px; margin-bottom: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .procesar-form h3 { margin-bottom: 15px; color: #2c3e50; }
        .procesar-form input { width: 65%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; margin-right: 10px; font-size: 14px; }
        .procesar-form button { padding: 12px 24px; background: #3498db; color: white; border: none; border-radius: 8px; cursor: pointer; margin: 5px; font-size: 14px; }
        .procesar-form button:hover { background: #2980b9; }
        .btn-video { background: #e67e22 !important; }
        .btn-video:hover { background: #d35400 !important; }
        
        .resultado { margin-top: 20px; padding: 20px; background: #e8f4f8; border-radius: 10px; display: none; }
        
        .content-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }
        .card { background: white; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }
        .card-header { background: #3498db; color: white; padding: 15px 20px; font-weight: bold; font-size: 18px; }
        .card-body { padding: 20px; max-height: 500px; overflow-y: auto; }
        
        .contenido-item { border-bottom: 1px solid #eee; padding: 15px; cursor: pointer; transition: background 0.2s; }
        .contenido-item:hover { background: #f8f9fa; }
        .contenido-item .categoria-badge { display: inline-block; padding: 3px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; margin-right: 10px; }
        .categoria-Construccion { background: #795548; color: white; }
        .categoria-Emprendimiento { background: #FF9800; color: white; }
        .categoria-Automejora { background: #9C27B0; color: white; }
        .categoria-Salud { background: #4CAF50; color: white; }
        .categoria-Construex-University { background: #2196F3; color: white; }
        
        .resumen-detalle { display: none; margin-top: 15px; padding: 15px; background: #f8f9fa; border-radius: 10px; }
        .resumen-detalle p { margin: 10px 0; line-height: 1.5; }
        
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1000; justify-content: center; align-items: center; }
        .modal-content { background: white; border-radius: 15px; max-width: 700px; width: 90%; max-height: 80vh; overflow-y: auto; padding: 25px; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 15px; margin-bottom: 15px; }
        .modal-close { cursor: pointer; font-size: 24px; color: #999; }
        .modal-close:hover { color: #333; }
        
        .video-card { background: #f8f9fa; border-radius: 10px; padding: 15px; margin-bottom: 15px; }
        .video-placeholder { background: #2c3e50; color: white; padding: 40px; text-align: center; border-radius: 10px; }
        
        button { cursor: pointer; }
        .loading { text-align: center; padding: 40px; color: #999; }
        
        @media (max-width: 768px) { .content-grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏗️ Construex Ecosystem</h1>
        <div class="subtitle">Sistema de clasificación y generación de contenido con IA</div>
        
        <div class="procesar-form">
            <h3>📎 Procesar nuevo enlace</h3>
            <input type="text" id="urlInput" placeholder="https://ejemplo.com/articulo">
            <button onclick="procesar(false)">📄 Solo resumen</button>
            <button class="btn-video" onclick="procesar(true)">🎬 Generar video</button>
            <button onclick="cargarDatos()">🔄 Actualizar</button>
            <div id="resultado" class="resultado"></div>
        </div>
        
        <div class="stats-grid" id="stats"></div>
        
        <div class="content-grid">
            <div class="card">
                <div class="card-header">📋 Últimos contenidos analizados</div>
                <div class="card-body" id="ultimosContenidos"></div>
            </div>
            <div class="card">
                <div class="card-header">🎬 Prompts para Higgsfield</div>
                <div class="card-body" id="higgsfieldPrompts"></div>
            </div>
        </div>
    </div>
    
    <!-- Modal para ver detalle -->
    <div id="detalleModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>📄 Detalle del contenido</h2>
                <span class="modal-close" onclick="cerrarModal()">&times;</span>
            </div>
            <div id="modalBody"></div>
        </div>
    </div>
    
    <script>
        let currentData = null;
        
        async function procesar(conVideo) {
            const url = document.getElementById('urlInput').value;
            if (!url) { alert('Ingresa una URL'); return; }
            
            const resultadoDiv = document.getElementById('resultado');
            resultadoDiv.style.display = 'block';
            resultadoDiv.innerHTML = '<div class="loading">⏳ Procesando enlace... Esto puede tomar unos segundos.</div>';
            
            try {
                const response = await fetch('/procesar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mensaje: url, generar_video: conVideo })
                });
                const data = await response.json();
                
                if (data.exito) {
                    let html = `<div style="background: #d4edda; padding: 15px; border-radius: 8px;">`;
                    html += `<strong>✅ Procesado correctamente</strong><br>`;
                    html += `📁 <strong>Categoría:</strong> ${data.categoria}<br>`;
                    html += `🔥 <strong>Viralidad potencial:</strong> ${data.viralidad}/10<br>`;
                    html += `📝 <strong>Resumen:</strong><br>${data.resumen ? data.resumen.substring(0, 300) + '...' : 'No disponible'}<br>`;
                    if (data.video_url) {
                        html += `🎬 <strong>Video generado:</strong> <a href="${data.video_url}" target="_blank">Ver video</a><br>`;
                    }
                    html += `<button onclick="verDetalle('${data.url}')" style="margin-top: 10px; background: #3498db; color: white; border: none; padding: 8px 16px; border-radius: 5px; cursor: pointer;">📖 Ver detalle completo</button>`;
                    html += `</div>`;
                    resultadoDiv.innerHTML = html;
                    cargarDatos();
                    document.getElementById('urlInput').value = '';
                } else {
                    resultadoDiv.innerHTML = `<div style="background: #f8d7da; padding: 15px; border-radius: 8px;"><strong>❌ Error:</strong> ${data.error || 'No se pudo procesar'}</div>`;
                }
            } catch(e) {
                resultadoDiv.innerHTML = `<div style="background: #f8d7da; padding: 15px; border-radius: 8px;"><strong>❌ Error:</strong> ${e.message}</div>`;
            }
        }
        
        async function cargarDatos() {
            await cargarEstadisticas();
            await cargarUltimos();
            await cargarHiggsfield();
        }
        
        async function cargarEstadisticas() {
            try {
                const response = await fetch('/estadisticas');
                const stats = await response.json();
                document.getElementById('stats').innerHTML = `
                    <div class="stat-card"><div class="stat-number">${stats.total || 0}</div><div class="stat-label">Total analizados</div></div>
                    <div class="stat-card"><div class="stat-number">${stats.viral_promedio || 0}/10</div><div class="stat-label">Viralidad promedio</div></div>
                    <div class="stat-card"><div class="stat-number">${Object.keys(stats.por_categoria || {}).length}</div><div class="stat-label">Categorías</div></div>
                `;
            } catch(e) { console.error(e); }
        }
        
        async function cargarUltimos() {
            try {
                const response = await fetch('/ultimos');
                const data = await response.json();
                if (data.ultimos && data.ultimos.length > 0) {
                    let html = '';
                    for (let item of data.ultimos) {
                        let categoriaClass = `categoria-${item.categoria.replace(/ /g, '-')}`;
                        html += `
                            <div class="contenido-item" onclick="verDetalle('${item.url}')">
                                <span class="categoria-badge ${categoriaClass}">${item.categoria}</span>
                                <strong>${item.titulo ? item.titulo.substring(0, 80) : 'Sin título'}</strong>
                                <div style="font-size: 12px; color: #999; margin-top: 8px;">📅 ${item.fecha ? item.fecha.substring(0, 19) : ''}</div>
                                <div class="resumen-detalle" id="detalle-${item.id}">
                                    <p><strong>Resumen completo:</strong><br>${item.resumen || 'No disponible'}</p>
                                    <button onclick="event.stopPropagation(); descargarResumen('${item.archivo_resumen}')" style="background: #2ecc71; color: white; border: none; padding: 5px 10px; border-radius: 5px; cursor: pointer;">📥 Descargar resumen</button>
                                </div>
                            </div>
                        `;
                    }
                    document.getElementById('ultimosContenidos').innerHTML = html;
                } else {
                    document.getElementById('ultimosContenidos').innerHTML = '<div class="loading">No hay contenido procesado aún</div>';
                }
            } catch(e) { console.error(e); }
        }
        
        async function cargarHiggsfield() {
            try {
                const response = await fetch('/higgsfield');
                const data = await response.json();
                if (data.prompts_higgsfield && data.prompts_higgsfield.length > 0) {
                    let html = '';
                    for (let item of data.prompts_higgsfield) {
                        html += `
                            <div class="contenido-item">
                                <strong>${item}</strong>
                                <div style="font-size: 12px; color: #999; margin-top: 8px;">📄 Prompt listo para usar en Higgsfield</div>
                                <button onclick="descargarPrompt('${item}')" style="margin-top: 10px; background: #e67e22; color: white; border: none; padding: 5px 10px; border-radius: 5px; cursor: pointer;">📥 Descargar prompt</button>
                            </div>
                        `;
                    }
                    document.getElementById('higgsfieldPrompts').innerHTML = html;
                } else {
                    document.getElementById('higgsfieldPrompts').innerHTML = '<div class="loading">No hay prompts generados aún</div>';
                }
            } catch(e) { console.error(e); }
        }
        
        async function verDetalle(url) {
            try {
                const response = await fetch('/detalle?url=' + encodeURIComponent(url));
                const data = await response.json();
                if (data.exito) {
                    document.getElementById('modalBody').innerHTML = `
                        <h3>${data.titulo || 'Sin título'}</h3>
                        <p><strong>URL:</strong> <a href="${data.url}" target="_blank">${data.url}</a></p>
                        <p><strong>Categoría:</strong> <span class="categoria-badge categoria-${data.categoria.replace(/ /g, '-')}">${data.categoria}</span></p>
                        <p><strong>Subcategoría:</strong> ${data.subcategoria}</p>
                        <p><strong>Viralidad:</strong> ${data.viralidad}/10</p>
                        <p><strong>Fecha:</strong> ${data.fecha}</p>
                        <hr>
                        <h4>📝 Resumen completo</h4>
                        <p style="background: #f8f9fa; padding: 15px; border-radius: 8px;">${data.resumen || 'No disponible'}</p>
                        <hr>
                        <h4>🎬 Prompt para Higgsfield</h4>
                        <pre style="background: #f8f9fa; padding: 15px; border-radius: 8px; overflow-x: auto;">${JSON.stringify(data.prompt_higgsfield || {}, null, 2)}</pre>
                        <button onclick="descargarResumen('${data.archivo_resumen}')" style="background: #2ecc71; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; margin-right: 10px;">📥 Descargar resumen</button>
                        <button onclick="descargarPrompt('${data.archivo_higgsfield ? data.archivo_higgsfield.split('/').pop() : ''}')" style="background: #e67e22; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer;">📥 Descargar prompt Higgsfield</button>
                    `;
                    document.getElementById('detalleModal').style.display = 'flex';
                }
            } catch(e) {
                alert('Error al cargar detalle: ' + e.message);
            }
        }
        
        function cerrarModal() {
            document.getElementById('detalleModal').style.display = 'none';
        }
        
        function descargarResumen(archivo) {
            if (archivo) {
                window.open('/descargar?archivo=' + encodeURIComponent(archivo), '_blank');
            }
        }
        
        function descargarPrompt(archivo) {
            if (archivo) {
                window.open('/descargar?archivo=' + encodeURIComponent(archivo), '_blank');
            }
        }
        
        cargarDatos();
        setInterval(cargarDatos, 30000);
    </script>
</body>
</html>
"""

# ============================================
# ENDPOINTS ADICIONALES
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

@app.route('/ultimos', methods=['GET'])
def ultimos_contenidos():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id, fecha, url, titulo, categoria, subcategoria, viralidad, resumen, archivo_resumen FROM contenido ORDER BY id DESC LIMIT 20')
        ultimos = [dict(row) for row in cursor.fetchall()]
    except:
        ultimos = []
    conn.close()
    return jsonify({"ultimos": ultimos}), 200

@app.route('/estadisticas', methods=['GET'])
def estadisticas():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM contenido")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT categoria, COUNT(*) FROM contenido GROUP BY categoria")
        por_categoria = dict(cursor.fetchall())
        cursor.execute("SELECT AVG(viralidad) FROM contenido")
        viral_promedio = cursor.fetchone()[0] or 0
    except:
        total = 0
        por_categoria = {}
        viral_promedio = 0
    conn.close()
    return jsonify({
        "total": total, 
        "por_categoria": por_categoria,
        "viral_promedio": round(viral_promedio, 1)
    }), 200

@app.route('/higgsfield', methods=['GET'])
def listar_higgsfield():
    archivos = os.listdir(HIGGSFIELD_DIR) if os.path.exists(HIGGSFIELD_DIR) else []
    return jsonify({"prompts_higgsfield": archivos[-20:]}), 200

@app.route('/detalle', methods=['GET'])
def detalle_contenido():
    url = request.args.get('url', '')
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM contenido WHERE url = ? ORDER BY id DESC LIMIT 1', (url,))
    row = cursor.fetchone()
    conn.close()
    if row:
        resultado = dict(row)
        try:
            with open(resultado.get('archivo_higgsfield', ''), 'r') as f:
                prompt_data = json.load(f)
                resultado['prompt_higgsfield'] = prompt_data.get('prompt', {})
        except:
            resultado['prompt_higgsfield'] = {}
        return jsonify({"exito": True, **resultado}), 200
    return jsonify({"exito": False, "error": "No encontrado"}), 404

@app.route('/descargar', methods=['GET'])
def descargar_archivo():
    archivo_path = request.args.get('archivo', '')
    if os.path.exists(archivo_path):
        return send_file(archivo_path, as_attachment=True)
    return jsonify({"error": "Archivo no encontrado"}), 404

@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok", "message": "Sistema Construex funcionando"}), 200

# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    init_db()
    print("""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN CON VISUALIZACIÓN
======================================================================

FUNCIONALIDADES:
   ✅ Dashboard visual interactivo
   ✅ Ver resúmenes completos
   ✅ Descargar archivos generados
   ✅ Ver prompts para Higgsfield
   ✅ Procesar enlaces con o sin video

ACCESO: http://localhost:10000/

======================================================================
""")
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)