"""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN CON BD ROBUSTA
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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HIGGSFIELD_API_KEY = os.getenv("HIGGSFIELD_API_KEY", "72700186-4d90-427e-ab87-d01b13ea189b")

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

IMAGENES_DIR = os.path.join(BASE_DIR, "imagenes_generadas")
os.makedirs(IMAGENES_DIR, exist_ok=True)

AUDIOS_DIR = os.path.join(BASE_DIR, "audios_generados")
os.makedirs(AUDIOS_DIR, exist_ok=True)

PRESENTACIONES_DIR = os.path.join(BASE_DIR, "presentaciones_generadas")
os.makedirs(PRESENTACIONES_DIR, exist_ok=True)

DB_FILE = os.path.join(BASE_DIR, "construex.db")
url_cache = {}


def get_db():
    """Obtiene conexión a la BD y asegura que la tabla existe"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Crear tabla si no existe (SIEMPRE se ejecuta)
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
            infografia_url TEXT,
            podcast_url TEXT,
            presentacion_url TEXT,
            video_url TEXT,
            motor_ia TEXT,
            procesado BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    return conn


def init_db():
    """Inicializa la base de datos"""
    conn = get_db()
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
    if any(p in texto for p in ["construc", "centro comercial", "mall", "obra", "empleo", "vacante"]):
        return "Construccion", "Proyectos", 8
    elif any(p in texto for p in ["negocio", "emprend", "empresa", "ventas", "inversion"]):
        return "Emprendimiento", "Negocios", 7
    elif any(p in texto for p in ["curso", "aprender", "educacion", "certificacion"]):
        return "Construex University", "Cursos", 6
    elif any(p in texto for p in ["salud", "medico", "bienestar", "dieta", "ejercicio"]):
        return "Salud", "Bienestar", 6
    return "Automejora", "Crecimiento", 5


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


def generar_infografia(titulo, resumen, categoria):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
    filename = f"infografia_{timestamp}_{nombre_limpio}.txt"
    filepath = os.path.join(IMAGENES_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"""INFOGRAFÍA GENERADA
Título: {titulo}
Categoría: {categoria}
Resumen: {resumen[:500]}
""")
    return filepath


def generar_podcast(titulo, resumen, categoria):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
    filename = f"podcast_{timestamp}_{nombre_limpio}.txt"
    filepath = os.path.join(AUDIOS_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"""PODCAST GENERADO
Título: {titulo}
Categoría: {categoria}
Guion: {resumen[:500]}
""")
    return filepath


def generar_presentacion(titulo, resumen, categoria):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
    filename = f"presentacion_{timestamp}_{nombre_limpio}.txt"
    filepath = os.path.join(PRESENTACIONES_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"""PRESENTACIÓN GENERADA
Título: {titulo}
Categoría: {categoria}
Contenido: {resumen[:500]}
""")
    return filepath


def generar_video(titulo, resumen, categoria):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
    filename = f"video_{timestamp}_{nombre_limpio}.txt"
    filepath = os.path.join(VIDEOS_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"""VIDEO GENERADO
Título: {titulo}
Categoría: {categoria}
Prompt para Higgsfield: {resumen[:500]}
""")
    return filepath


def guardar_en_db(url, titulo, dominio, categoria, subcategoria, viralidad, resumen, 
                  archivo_resumen, archivo_higgsfield, infografia_url, podcast_url, 
                  presentacion_url, video_url, motor_ia):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO contenido (
            fecha, url, titulo, dominio, categoria, subcategoria, viralidad,
            resumen, archivo_resumen, archivo_higgsfield, infografia_url, podcast_url,
            presentacion_url, video_url, motor_ia, procesado
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        infografia_url,
        podcast_url,
        presentacion_url,
        video_url,
        motor_ia,
        1
    ))
    conn.commit()
    conn.close()
    print("   ✅ Datos guardados en BD")


def procesar_enlace_completo(url, opciones=None):
    if opciones is None:
        opciones = {'video': False, 'infografia': False, 'podcast': False, 'presentacion': False}
    
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

        resumen = f"Resumen del artículo: {contenido['descripcion'][:500]}"
        resultado['resumen'] = resumen

        archivo_resumen = guardar_resumen(contenido['titulo'], categoria, subcategoria, resumen, url)
        resultado['archivo_resumen'] = archivo_resumen

        prompt_higgsfield = {
            "video_prompt": f"Video sobre {categoria}: {contenido['titulo'][:100]}",
            "duration": 20,
            "aspect_ratio": "9:16",
            "style": "educational",
            "text_overlay": f"Aprende sobre {categoria}"
        }
        archivo_higgsfield = guardar_prompt_higgsfield(contenido['titulo'], categoria, subcategoria, prompt_higgsfield, url)
        resultado['archivo_higgsfield'] = archivo_higgsfield
        resultado['prompt_higgsfield'] = prompt_higgsfield

        # Generar contenido adicional
        if opciones.get('infografia'):
            infografia_url = generar_infografia(contenido['titulo'], resumen, categoria)
            resultado['infografia_url'] = infografia_url
        
        if opciones.get('podcast'):
            podcast_url = generar_podcast(contenido['titulo'], resumen, categoria)
            resultado['podcast_url'] = podcast_url
        
        if opciones.get('presentacion'):
            presentacion_url = generar_presentacion(contenido['titulo'], resumen, categoria)
            resultado['presentacion_url'] = presentacion_url
        
        if opciones.get('video'):
            video_url = generar_video(contenido['titulo'], resumen, categoria)
            resultado['video_url'] = video_url

        # Guardar en BD
        guardar_en_db(
            url, contenido['titulo'], contenido['dominio'],
            categoria, subcategoria, viralidad, resumen,
            archivo_resumen, archivo_higgsfield,
            resultado.get('infografia_url'), resultado.get('podcast_url'),
            resultado.get('presentacion_url'), resultado.get('video_url'),
            "manual"
        )

        return resultado

    except Exception as e:
        print(f"   ❌ Error: {e}")
        resultado['exito'] = False
        resultado['error'] = str(e)
        return resultado


# ============================================
# DASHBOARD HTML
# ============================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Construex Ecosystem</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f0f2f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #2c3e50; }
        .card { background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .checkbox-group { display: flex; gap: 20px; margin: 15px 0; flex-wrap: wrap; }
        .checkbox-group label { display: flex; align-items: center; gap: 5px; cursor: pointer; }
        input[type="text"] { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; margin-bottom: 10px; font-size: 14px; }
        button { padding: 12px 24px; background: #3498db; color: white; border: none; border-radius: 5px; cursor: pointer; margin: 5px; }
        button:hover { background: #2980b9; }
        .btn-generar { background: #27ae60; }
        .btn-generar:hover { background: #229954; }
        .resultado { margin-top: 20px; padding: 15px; background: #e8f4f8; border-radius: 5px; display: none; }
        .stats-grid { display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }
        .stat-card { background: white; padding: 20px; border-radius: 10px; text-align: center; flex: 1; min-width: 150px; }
        .stat-number { font-size: 32px; font-weight: bold; color: #3498db; }
        .contenido-item { border-bottom: 1px solid #eee; padding: 10px; cursor: pointer; }
        .contenido-item:hover { background: #f8f9fa; }
        .categoria-badge { display: inline-block; padding: 3px 10px; border-radius: 15px; font-size: 11px; font-weight: bold; margin-right: 10px; }
        .Construccion { background: #795548; color: white; }
        .Emprendimiento { background: #FF9800; color: white; }
        .Automejora { background: #9C27B0; color: white; }
        .Salud { background: #4CAF50; color: white; }
        .Construex-University { background: #2196F3; color: white; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1000; justify-content: center; align-items: center; }
        .modal-content { background: white; border-radius: 10px; max-width: 700px; width: 90%; max-height: 80vh; overflow-y: auto; padding: 20px; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 10px; margin-bottom: 15px; }
        .modal-close { cursor: pointer; font-size: 24px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏗️ Construex Ecosystem</h1>
        
        <div class="card">
            <h3>📎 Procesar nuevo enlace</h3>
            <input type="text" id="urlInput" placeholder="https://ejemplo.com/articulo">
            
            <div class="checkbox-group">
                <label><input type="checkbox" id="infografia"> 🖼️ Infografía</label>
                <label><input type="checkbox" id="podcast"> 🎙️ Podcast</label>
                <label><input type="checkbox" id="presentacion"> 📊 Presentación</label>
                <label><input type="checkbox" id="video"> 🎬 Video</label>
            </div>
            
            <button class="btn-generar" onclick="procesarTodo()">🚀 Procesar y generar TODO</button>
            <button onclick="cargarDatos()">🔄 Actualizar</button>
            <div id="resultado" class="resultado"></div>
        </div>
        
        <div class="stats-grid" id="stats"></div>
        
        <div class="card">
            <h3>📋 Últimos contenidos</h3>
            <div id="ultimos"></div>
        </div>
    </div>
    
    <div id="detalleModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>📄 Detalle</h2>
                <span class="modal-close" onclick="cerrarModal()">&times;</span>
            </div>
            <div id="modalBody"></div>
        </div>
    </div>
    
    <script>
        async function procesarTodo() {
            const url = document.getElementById('urlInput').value;
            if (!url) { alert('Ingresa una URL'); return; }
            
            const opciones = {
                mensaje: url,
                generar_infografia: document.getElementById('infografia').checked,
                generar_podcast: document.getElementById('podcast').checked,
                generar_presentacion: document.getElementById('presentacion').checked,
                generar_video: document.getElementById('video').checked
            };
            
            const resultadoDiv = document.getElementById('resultado');
            resultadoDiv.style.display = 'block';
            resultadoDiv.innerHTML = '⏳ Procesando...';
            
            try {
                const response = await fetch('/procesar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(opciones)
                });
                const data = await response.json();
                
                if (data.exito) {
                    let html = `<div style="background:#d4edda; padding:15px; border-radius:8px;">`;
                    html += `<strong>✅ Procesado correctamente</strong><br>`;
                    html += `📁 Categoría: ${data.categoria}<br>`;
                    html += `🔥 Viralidad: ${data.viralidad}/10<br>`;
                    if (data.infografia_url) html += `🖼️ Infografía: <a href="${data.infografia_url}" target="_blank">Descargar</a><br>`;
                    if (data.podcast_url) html += `🎙️ Podcast: <a href="${data.podcast_url}" target="_blank">Descargar</a><br>`;
                    if (data.presentacion_url) html += `📊 Presentación: <a href="${data.presentacion_url}" target="_blank">Descargar</a><br>`;
                    if (data.video_url) html += `🎬 Video: <a href="${data.video_url}" target="_blank">Descargar</a><br>`;
                    html += `<button onclick="verDetalle('${data.url}')">📖 Ver detalle</button></div>`;
                    resultadoDiv.innerHTML = html;
                    cargarDatos();
                    document.getElementById('urlInput').value = '';
                } else {
                    resultadoDiv.innerHTML = `<div style="background:#f8d7da; padding:15px; border-radius:8px;">❌ Error: ${data.error}</div>`;
                }
            } catch(e) {
                resultadoDiv.innerHTML = `<div style="background:#f8d7da; padding:15px; border-radius:8px;">❌ Error: ${e.message}</div>`;
            }
        }
        
        async function cargarDatos() {
            try {
                const statsRes = await fetch('/estadisticas');
                const stats = await statsRes.json();
                document.getElementById('stats').innerHTML = `
                    <div class="stat-card"><div class="stat-number">${stats.total || 0}</div><div>Total</div></div>
                    <div class="stat-card"><div class="stat-number">${stats.viral_promedio || 0}/10</div><div>Viralidad promedio</div></div>
                `;
                
                const ultimosRes = await fetch('/ultimos');
                const ultimos = await ultimosRes.json();
                if (ultimos.ultimos && ultimos.ultimos.length > 0) {
                    let html = '';
                    for (let item of ultimos.ultimos) {
                        html += `<div class="contenido-item" onclick="verDetalle('${item.url}')">
                            <span class="categoria-badge ${item.categoria}">${item.categoria}</span>
                            <strong>${item.titulo ? item.titulo.substring(0, 60) : 'Sin título'}</strong>
                            <div style="font-size: 11px; color:#999;">${item.fecha ? item.fecha.substring(0, 19) : ''}</div>
                        </div>`;
                    }
                    document.getElementById('ultimos').innerHTML = html;
                } else {
                    document.getElementById('ultimos').innerHTML = '<p>No hay contenido</p>';
                }
            } catch(e) { console.error(e); }
        }
        
        async function verDetalle(url) {
            try {
                const response = await fetch('/detalle?url=' + encodeURIComponent(url));
                const data = await response.json();
                if (data.exito) {
                    let html = `<h3>${data.titulo || 'Sin título'}</h3>
                        <p><strong>Categoría:</strong> ${data.categoria}</p>
                        <p><strong>Viralidad:</strong> ${data.viralidad}/10</p>
                        <p><strong>Resumen:</strong> ${data.resumen || 'No disponible'}</p>`;
                    if (data.infografia_url) html += `<p><a href="${data.infografia_url}" target="_blank">📥 Infografía</a></p>`;
                    if (data.podcast_url) html += `<p><a href="${data.podcast_url}" target="_blank">🎙️ Podcast</a></p>`;
                    if (data.presentacion_url) html += `<p><a href="${data.presentacion_url}" target="_blank">📊 Presentación</a></p>`;
                    if (data.video_url) html += `<p><a href="${data.video_url}" target="_blank">🎬 Video</a></p>`;
                    document.getElementById('modalBody').innerHTML = html;
                    document.getElementById('detalleModal').style.display = 'flex';
                }
            } catch(e) { alert('Error: ' + e.message); }
        }
        
        function cerrarModal() { document.getElementById('detalleModal').style.display = 'none'; }
        
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
    return jsonify({"status": "ok"}), 200


@app.route('/procesar', methods=['POST'])
def procesar():
    data = request.get_json()
    mensaje = data.get('mensaje', '')
    
    opciones = {
        'infografia': data.get('generar_infografia', False),
        'podcast': data.get('generar_podcast', False),
        'presentacion': data.get('generar_presentacion', False),
        'video': data.get('generar_video', False)
    }
    
    if not mensaje:
        return jsonify({"error": "No hay mensaje"}), 400
    enlaces = extraer_enlaces(mensaje)
    if not enlaces:
        return jsonify({"error": "No se encontraron enlaces"}), 400
    resultado = procesar_enlace_completo(enlaces[0], opciones)
    return jsonify(resultado), 200


@app.route('/ultimos', methods=['GET'])
def ultimos_contenidos():
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT fecha, url, titulo, categoria FROM contenido ORDER BY id DESC LIMIT 20')
    ultimos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"ultimos": ultimos}), 200


@app.route('/estadisticas', methods=['GET'])
def estadisticas():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM contenido")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT AVG(viralidad) FROM contenido")
    viral_promedio = cursor.fetchone()[0] or 0
    conn.close()
    return jsonify({"total": total, "viral_promedio": round(viral_promedio, 1)}), 200


@app.route('/detalle', methods=['GET'])
def detalle_contenido():
    url = request.args.get('url', '')
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM contenido WHERE url = ? ORDER BY id DESC LIMIT 1', (url,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return jsonify({"exito": True, **dict(row)}), 200
    return jsonify({"exito": False, "error": "No encontrado"}), 404


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
         CONSTRUEX ECOSYSTEM - FUNCIONANDO
======================================================================
""")
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)