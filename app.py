"""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN FINAL COMPLETA
======================================================================
Funcionalidades:
- Clasificación de enlaces en 5 categorías
- Generación de resúmenes para Notebook LM
- Generación de prompts para Higgsfield (videos)
- Generación automática de videos (opcional)
- Preparación de contenido para redes sociales
- Dashboard web visual
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

# APIs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")
HIGGSFIELD_API_KEY = os.getenv("HIGGSFIELD_API_KEY", "72700186-4d90-427e-ab87-d01b13ea189b")
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
# FUNCIONES DE EXTRACCION
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

# ============================================
# CLASIFICACION
# ============================================

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
# GUARDADO DE ARCHIVOS
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

# ============================================
# GENERACION DE PROMPTS PARA HIGGSFIELD
# ============================================

def generar_prompt_higgsfield(titulo, resumen, categoria, subcategoria, viralidad):
    """Genera un prompt detallado para Higgsfield"""
    return {
        "video_prompt": f"Video educativo sobre {categoria}: {titulo[:100]}.\nContenido: {resumen[:300]}.\nUsa un tono profesional y claro.",
        "duration": 20,
        "aspect_ratio": "9:16",
        "style": "educational",
        "text_overlay": f"Aprende sobre {categoria}",
        "hashtags": [f"#{categoria.replace(' ', '')}", "#Construex", "#Educacion"],
        "color_palette": ["#2c3e50", "#3498db"],
        "camera_movement": "slow zoom",
        "music_mood": "inspirational"
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
            "titulo": titulo,
            "viralidad": prompt_data.get("duration", 20)
        },
        "prompt": prompt_data,
        "guia_publicacion": {
            "mejor_plataforma": "TikTok" if prompt_data.get("duration", 20) <= 20 else "Instagram Reels",
            "mejor_horario": "19:00 - 21:00",
            "hashtags_sugeridos": prompt_data.get("hashtags", [f"#{categoria.replace(' ', '')}"])
        }
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(contenido, f, ensure_ascii=False, indent=2)

    return filepath

# ============================================
# GENERACION DE VIDEOS CON HIGGSFIELD
# ============================================

def generar_video_con_higgsfield(prompt_data, titulo, categoria):
    if not HIGGSFIELD_API_KEY:
        print("   ⚠️ Higgsfield API key no configurada")
        return None

    headers = {
        "Authorization": f"Bearer {HIGGSFIELD_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": prompt_data.get("video_prompt", ""),
        "duration": prompt_data.get("duration", 15),
        "aspect_ratio": prompt_data.get("aspect_ratio", "9:16"),
        "style": prompt_data.get("style", "educational")
    }

    try:
        print("   🎬 Generando video con Higgsfield...")
        response = requests.post(HIGGSFIELD_API_URL, headers=headers, json=payload, timeout=120)

        if response.status_code == 200:
            result = response.json()
            video_url = result.get("video_url") or result.get("output_url") or result.get("url")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
            video_info = {
                "titulo": titulo,
                "categoria": categoria,
                "url": video_url,
                "created_at": datetime.now().isoformat(),
                "prompt_usado": prompt_data
            }

            info_path = os.path.join(VIDEOS_DIR, f"{timestamp}_{nombre_limpio}.json")
            with open(info_path, 'w', encoding='utf-8') as f:
                json.dump(video_info, f, ensure_ascii=False, indent=2)

            print(f"   ✅ Video generado: {video_url}")
            return video_url
        else:
            print(f"   ❌ Error Higgsfield: {response.status_code}")
            return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

# ============================================
# PREPARACION PARA REDES SOCIALES
# ============================================

def preparar_publicacion_redes(titulo, resumen, categoria, viralidad, video_url=None):
    publicaciones = {
        "instagram": {
            "caption": f"✨ {titulo[:100]}\n\n{resumen[:300]}\n\n#{categoria.replace(' ', '')} #Construex #Educacion",
            "url": video_url
        },
        "tiktok": {
            "description": f"{resumen[:150]} #{categoria.replace(' ', '')} #Construex",
            "url": video_url
        },
        "twitter": {
            "text": f"{titulo[:100]}\n\n{resumen[:240]}\n\n#{categoria.replace(' ', '')} #Construex",
            "url": video_url
        },
        "linkedin": {
            "text": f"📌 {titulo[:120]}\n\n{resumen[:500]}\n\n#{categoria.replace(' ', '')} #Construex",
            "url": video_url
        }
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
    pub_path = os.path.join(VIDEOS_DIR, f"publicacion_{timestamp}_{nombre_limpio}.json")

    with open(pub_path, 'w', encoding='utf-8') as f:
        json.dump(publicaciones, f, ensure_ascii=False, indent=2)

    return publicaciones, pub_path

# ============================================
# GUARDADO EN BASE DE DATOS
# ============================================

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

# ============================================
# PROCESAMIENTO COMPLETO
# ============================================

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

        # Guardar resumen
        archivo_resumen = guardar_resumen(
            contenido['titulo'],
            categoria,
            subcategoria,
            resumen,
            url
        )
        resultado['archivo_resumen'] = archivo_resumen

        # Generar prompt para Higgsfield
        print("   🎬 Generando prompt para Higgsfield...")
        prompt_higgsfield = generar_prompt_higgsfield(
            contenido['titulo'],
            resumen,
            categoria,
            subcategoria,
            viralidad
        )
        archivo_higgsfield = guardar_prompt_higgsfield(
            contenido['titulo'],
            categoria,
            subcategoria,
            prompt_higgsfield,
            url
        )
        resultado['archivo_higgsfield'] = archivo_higgsfield
        resultado['prompt_higgsfield'] = prompt_higgsfield

        # Generar video (opcional)
        video_url = None
        if generar_video and HIGGSFIELD_API_KEY:
            video_url = generar_video_con_higgsfield(prompt_higgsfield, contenido['titulo'], categoria)
            resultado['video_url'] = video_url

            if video_url:
                publicaciones, pub_path = preparar_publicacion_redes(
                    contenido['titulo'],
                    resumen,
                    categoria,
                    viralidad,
                    video_url
                )
                resultado['publicaciones'] = publicaciones
                resultado['archivo_publicacion'] = pub_path

        # Guardar en BD
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
    <title>Construex Ecosystem - Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f0f2f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #2c3e50; }
        .card { background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        input { width: 60%; padding: 12px; margin-right: 10px; border: 1px solid #ddd; border-radius: 5px; }
        button { background: #3498db; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; margin: 5px; }
        .resultado { margin-top: 20px; padding: 15px; background: #e8f4f8; border-radius: 5px; display: none; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #3498db; color: white; }
        .stat { display: inline-block; background: #3498db; color: white; padding: 15px; margin: 10px; border-radius: 8px; min-width: 150px; text-align: center; }
        .stat-number { font-size: 28px; font-weight: bold; }
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
            <input type="text" id="urlInput" placeholder="https://ejemplo.com/articulo" style="width: 60%;">
            <button onclick="procesar(false)">Procesar (solo resumen)</button>
            <button onclick="procesar(true)" style="background: #e67e22;">Procesar + Video</button>
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
    </div>

    <script>
        async function procesar(conVideo) {
            const url = document.getElementById('urlInput').value;
            if (!url) { alert('Ingresa una URL'); return; }

            const resultadoDiv = document.getElementById('resultado');
            resultadoDiv.style.display = 'block';
            resultadoDiv.innerHTML = 'Procesando... Esto puede tomar unos segundos...';

            try {
                const response = await fetch('/procesar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mensaje: url, generar_video: conVideo })
                });
                const data = await response.json();

                if (data.exito) {
                    let html = `<strong>✅ Procesado correctamente</strong><br>`;
                    html += `📁 Categoría: ${data.categoria}<br>`;
                    html += `🔥 Viralidad: ${data.viralidad}/10<br>`;
                    html += `📄 Resumen: ${data.resumen ? data.resumen.substring(0, 200) + '...' : 'No disponible'}<br>`;
                    if (data.video_url) {
                        html += `🎬 Video generado: <a href="${data.video_url}" target="_blank">Ver video</a><br>`;
                    }
                    resultadoDiv.innerHTML = html;
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
                    let html = '<table><th>Fecha</th><th>Título</th><th>Categoría</th></tr>';
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
        cursor.execute('SELECT fecha, url, titulo, categoria FROM contenido ORDER BY id DESC LIMIT 20')
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
        cursor.execute("SELECT AVG(viralidad) FROM contenido")
        viral_promedio = cursor.fetchone()[0] or 0
    except:
        total = 0
        viral_promedio = 0
    conn.close()
    return jsonify({"total": total, "viral_promedio": round(viral_promedio, 1)}), 200

@app.route('/higgsfield', methods=['GET'])
def listar_higgsfield():
    archivos = os.listdir(HIGGSFIELD_DIR) if os.path.exists(HIGGSFIELD_DIR) else []
    return jsonify({"prompts_higgsfield": archivos[-20:]}), 200

@app.route('/videos', methods=['GET'])
def listar_videos():
    archivos = os.listdir(VIDEOS_DIR) if os.path.exists(VIDEOS_DIR) else []
    videos_info = []
    for archivo in archivos:
        if archivo.endswith('.json') and 'publicacion' not in archivo:
            try:
                with open(os.path.join(VIDEOS_DIR, archivo), 'r') as f:
                    videos_info.append(json.load(f))
            except:
                pass
    return jsonify({"videos": videos_info[-20:]}), 200

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
         CONSTRUEX ECOSYSTEM - VERSIÓN FINAL COMPLETA
======================================================================

FUNCIONALIDADES:
   ✅ Procesar enlaces (POST /procesar)
   ✅ Generar resúmenes para Notebook LM
   ✅ Generar prompts para Higgsfield
   ✅ Generar videos (opcional)
   ✅ Preparar publicaciones para redes sociales
   ✅ Dashboard visual (/)

======================================================================
""")
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)