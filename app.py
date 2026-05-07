"""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN FINAL DEFINITIVA
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
# CONFIGURACION
# ============================================

WHATSAPP_VERIFY_TOKEN = "construex_verify_2026"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")

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
    if any(p in texto for p in ["arquitect", "construc", "obra", "cemento", "archdaily", "building"]):
        return "Construccion", "Proyectos", 7
    elif any(p in texto for p in ["negocio", "emprend", "empresa", "ventas", "startup"]):
        return "Emprendimiento", "Negocios", 7
    elif any(p in texto for p in ["curso", "aprender", "educacion", "certificacion", "taller"]):
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
        print(f"   📄 Título: {contenido['titulo'][:60]}...")

        categoria, subcategoria, viralidad = clasificar_manual(
            contenido['titulo'],
            contenido['descripcion'],
            contenido['dominio']
        )

        resultado['categoria'] = categoria
        resultado['subcategoria'] = subcategoria
        resultado['viralidad'] = viralidad
        resultado['motor_usado'] = "manual"

        print(f"   📁 Categoría: {categoria} > {subcategoria}")

        resumen = f"Resumen de '{contenido['titulo']}': {contenido['descripcion'][:500]}"
        resultado['resumen'] = resumen

        archivo_resumen = guardar_resumen(
            contenido['titulo'],
            categoria,
            subcategoria,
            resumen,
            url
        )
        resultado['archivo_resumen'] = archivo_resumen

        archivo_higgsfield = guardar_prompt_higgsfield(
            contenido['titulo'],
            categoria,
            subcategoria,
            url
        )
        resultado['archivo_higgsfield'] = archivo_higgsfield

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
            "manual"
        )

        return resultado

    except Exception as e:
        print(f"   ❌ Error: {e}")
        resultado['exito'] = False
        resultado['error'] = str(e)
        return resultado


# ============================================
# DASHBOARD HTML (VERSIÓN SIMPLIFICADA QUE FUNCIONA)
# ============================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Construex Ecosystem - Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f0f2f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #2c3e50; }
        .card { background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stat { display: inline-block; background: #3498db; color: white; padding: 15px; margin: 10px; border-radius: 8px; min-width: 150px; text-align: center; }
        .stat-number { font-size: 28px; font-weight: bold; }
        input { width: 70%; padding: 12px; margin-right: 10px; border: 1px solid #ddd; border-radius: 5px; }
        button { background: #3498db; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; }
        .resultado { margin-top: 20px; padding: 15px; background: #e8f4f8; border-radius: 5px; display: none; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #3498db; color: white; }
        .categoria-Construccion { background: #795548; color: white; padding: 3px 8px; border-radius: 12px; display: inline-block; }
        .categoria-Emprendimiento { background: #FF9800; color: white; padding: 3px 8px; border-radius: 12px; display: inline-block; }
        .categoria-Automejora { background: #9C27B0; color: white; padding: 3px 8px; border-radius: 12px; display: inline-block; }
        .categoria-Salud { background: #4CAF50; color: white; padding: 3px 8px; border-radius: 12px; display: inline-block; }
        .categoria-Construex-University { background: #2196F3; color: white; padding: 3px 8px; border-radius: 12px; display: inline-block; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏗️ Construex Ecosystem</h1>
        
        <div class="card">
            <h3>Procesar nuevo enlace</h3>
            <input type="text" id="urlInput" placeholder="https://ejemplo.com/articulo" style="width: 70%;">
            <button onclick="procesar()">Procesar</button>
            <button onclick="cargarDatos()">Actualizar</button>
            <div id="resultado" class="resultado"></div>
        </div>
        
        <div class="card">
            <h3>Estadísticas</h3>
            <div id="stats"></div>
        </div>
        
        <div class="card">
            <h3>Últimos contenidos analizados</h3>
            <div id="ultimos"></div>
        </div>
        
        <div class="card">
            <h3>Prompts generados para Higgsfield</h3>
            <div id="higgsfield"></div>
        </div>
    </div>
    
    <script>
        async function procesar() {
            const url = document.getElementById('urlInput').value;
            if (!url) { alert('Ingresa una URL'); return; }
            
            const resultadoDiv = document.getElementById('resultado');
            resultadoDiv.style.display = 'block';
            resultadoDiv.innerHTML = 'Procesando...';
            
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
                        Categoría: ${data.categoria}<br>
                        Subcategoría: ${data.subcategoria}<br>
                        Viralidad: ${data.viralidad}/10<br>
                        Motor usado: ${data.motor_usado || 'manual'}
                    `;
                    cargarDatos();
                    document.getElementById('urlInput').value = '';
                } else {
                    resultadoDiv.innerHTML = `<strong>❌ Error:</strong> ${data.error || 'No se pudo procesar'}`;
                }
            } catch(e) {
                resultadoDiv.innerHTML = `<strong>❌ Error:</strong> ${e.message}`;
            }
        }
        
        async function cargarDatos() {
            try {
                const statsRes = await fetch('/estadisticas');
                const stats = await statsRes.json();
                document.getElementById('stats').innerHTML = `
                    <div class="stat"><div class="stat-number">${stats.total || 0}</div><div>Total analizados</div></div>
                    <div class="stat"><div class="stat-number">${stats.viral_promedio || 0}/10</div><div>Viralidad promedio</div></div>
                `;
                
                const ultimosRes = await fetch('/ultimos');
                const ultimos = await ultimosRes.json();
                if (ultimos.ultimos && ultimos.ultimos.length > 0) {
                    let html = '<table><tr><th>Fecha</th><th>Título</th><th>Categoría</th></tr>';
                    for (let item of ultimos.ultimos) {
                        html += `<tr>
                            <td>${item.fecha ? item.fecha.substring(0, 19) : ''}</td>
                            <td>${item.titulo ? item.titulo.substring(0, 60) : 'Sin título'}</td>
                            <td><span class="categoria-${item.categoria.replace(/ /g, '-')}">${item.categoria}</span></td>
                        </tr>`;
                    }
                    html += '</table>';
                    document.getElementById('ultimos').innerHTML = html;
                } else {
                    document.getElementById('ultimos').innerHTML = '<p>No hay contenido procesado aún</p>';
                }
                
                const hgRes = await fetch('/higgsfield');
                const hg = await hgRes.json();
                if (hg.prompts_higgsfield && hg.prompts_higgsfield.length > 0) {
                    let html = '<ul>';
                    for (let item of hg.prompts_higgsfield) {
                        html += `<li>${item}</li>`;
                    }
                    html += '</ul>';
                    document.getElementById('higgsfield').innerHTML = html;
                } else {
                    document.getElementById('higgsfield').innerHTML = '<p>No hay prompts generados aún</p>';
                }
            } catch(e) {
                console.error(e);
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
            estructura[cat] = os.listdir(path) if os.listdir(path) else []
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
    cursor.execute('SELECT fecha, url, titulo, categoria FROM contenido ORDER BY id DESC LIMIT 20')
    ultimos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"ultimos": ultimos}), 200


@app.route('/estadisticas', methods=['GET'])
def estadisticas():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM contenido")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT AVG(viralidad) FROM contenido")
    viral_promedio = cursor.fetchone()[0] or 0
    conn.close()
    return jsonify({"total": total, "viral_promedio": round(viral_promedio, 1)}), 200


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
         CONSTRUEX ECOSYSTEM - VERSIÓN FINAL DEFINITIVA
======================================================================

Dashboard: http://localhost:10000/
Webhook: /webhook
Procesar: POST /procesar

======================================================================
""")
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)