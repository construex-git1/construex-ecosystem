"""
======================================================================
         CONSTRUEX ECOSYSTEM - CON PROCESAMIENTO ASÍNCRONO
         Solución para timeout en Render
======================================================================
"""

import os
import re
import json
import requests
import sqlite3
import time
import uuid
import threading
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HIGGSFIELD_API_KEY = os.getenv("HIGGSFIELD_API_KEY", "72700186-4d90-427e-ab87-d01b13ea189b")

# Configurar Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    gemini_model = None

# Directorios
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGENES_DIR = os.path.join(BASE_DIR, "imagenes_generadas")
VIDEOS_DIR = os.path.join(BASE_DIR, "videos_generados")
CATEGORIAS_DIR = {
    "Salud": os.path.join(BASE_DIR, "contenido", "Salud"),
    "Emprendimiento": os.path.join(BASE_DIR, "contenido", "Emprendimiento"),
    "Automejora": os.path.join(BASE_DIR, "contenido", "Automejora"),
    "Construccion": os.path.join(BASE_DIR, "contenido", "Construccion"),
    "Construex University": os.path.join(BASE_DIR, "contenido", "Construex_University")
}

for carpeta in CATEGORIAS_DIR.values():
    os.makedirs(carpeta, exist_ok=True)
os.makedirs(IMAGENES_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)

DB_FILE = os.path.join(BASE_DIR, "construex.db")
url_cache = {}

# Cola de trabajos en memoria
trabajos = {}


def get_db():
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
            viralidad INTEGER,
            resumen TEXT,
            imagen_url TEXT,
            video_url TEXT,
            procesado BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    return conn


def init_db():
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
        response = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
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
        return clasificar_manual(titulo, descripcion, dominio)
    
    prompt = f"""
    Clasifica este contenido en UNA de estas 5 categorías:
    Salud, Emprendimiento, Automejora, Construccion, Construex University

    TITULO: {titulo}
    DOMINIO: {dominio}
    DESCRIPCION: {descripcion[:500]}

    Responde SOLO con el nombre de la categoría.
    """
    
    try:
        respuesta = gemini_model.generate_content(prompt)
        categoria = respuesta.text.strip()
        
        categorias_validas = ["Salud", "Emprendimiento", "Automejora", "Construccion", "Construex University"]
        for cat in categorias_validas:
            if cat in categoria:
                return cat, 7
        return "Automejora", 5
    except:
        return clasificar_manual(titulo, descripcion, dominio)


def clasificar_manual(titulo, descripcion, dominio):
    texto = f"{titulo} {descripcion}".lower()
    if any(p in texto for p in ["construc", "centro comercial", "mall", "obra", "empleo"]):
        return "Construccion", 8
    elif any(p in texto for p in ["negocio", "emprend", "empresa", "ventas"]):
        return "Emprendimiento", 7
    elif any(p in texto for p in ["curso", "aprender", "educacion"]):
        return "Construex University", 6
    elif any(p in texto for p in ["salud", "medico", "bienestar"]):
        return "Salud", 6
    return "Automejora", 5


def generar_resumen_con_gemini(titulo, descripcion):
    if not gemini_model:
        return f"Resumen: {descripcion[:500]}"
    
    prompt = f"""
    Genera un resumen ejecutivo de 3-4 líneas sobre:
    TITULO: {titulo}
    CONTENIDO: {descripcion[:800]}
    """
    
    try:
        respuesta = gemini_model.generate_content(prompt)
        return respuesta.text
    except:
        return descripcion[:500]


def generar_imagen_con_higgsfield(prompt_imagen, titulo, categoria):
    """Genera imagen usando Higgsfield"""
    if not HIGGSFIELD_API_KEY:
        return None
    
    headers = {
        "Authorization": f"Bearer {HIGGSFIELD_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "prompt": prompt_imagen,
        "width": 1080,
        "height": 1080,
        "num_inference_steps": 30,
        "guidance_scale": 7.5
    }
    
    try:
        print("   🖼️ Generando imagen...")
        response = requests.post(
            "https://api.higgsfield.ai/v1/images/generations",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            image_url = result.get("data", [{}])[0].get("url")
            
            if image_url:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
                filename = f"imagen_{timestamp}_{nombre_limpio}.png"
                filepath = os.path.join(IMAGENES_DIR, filename)
                
                img_response = requests.get(image_url)
                with open(filepath, 'wb') as f:
                    f.write(img_response.content)
                
                print(f"   ✅ Imagen guardada: {filepath}")
                return filepath
    except Exception as e:
        print(f"   ❌ Error imagen: {e}")
    
    return None


def generar_video_con_higgsfield(prompt_video, titulo, categoria):
    """Genera video usando Higgsfield"""
    if not HIGGSFIELD_API_KEY:
        return None
    
    headers = {
        "Authorization": f"Bearer {HIGGSFIELD_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "prompt": prompt_video,
        "duration": 10,
        "aspect_ratio": "9:16"
    }
    
    try:
        print("   🎬 Generando video...")
        response = requests.post(
            "https://api.higgsfield.ai/v1/video/generations",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 202:
            generation_id = response.json().get("id")
            print(f"   ⏳ Procesando video (ID: {generation_id})...")
            
            for i in range(60):
                time.sleep(5)
                status_response = requests.get(
                    f"https://api.higgsfield.ai/v1/video/generations/{generation_id}",
                    headers=headers
                )
                status_data = status_response.json()
                
                if status_data.get("status") == "completed":
                    video_url = status_data.get("output", {}).get("url")
                    print(f"   ✅ Video generado: {video_url}")
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
                    info_path = os.path.join(VIDEOS_DIR, f"video_{timestamp}_{nombre_limpio}.json")
                    
                    with open(info_path, 'w', encoding='utf-8') as f:
                        json.dump({
                            "titulo": titulo,
                            "categoria": categoria,
                            "url": video_url,
                            "created_at": datetime.now().isoformat()
                        }, f, ensure_ascii=False, indent=2)
                    
                    return video_url
                    
                elif status_data.get("status") == "failed":
                    print(f"   ❌ Error: {status_data.get('error')}")
                    return None
            
            return None
    except Exception as e:
        print(f"   ❌ Error video: {e}")
    
    return None


def crear_prompt_para_imagen(titulo, categoria, resumen):
    return f"""
    Imagen profesional para publicación en redes sociales.
    Tema: {titulo[:100]}
    Categoría: {categoria}
    Contexto: {resumen[:200]}
    Estilo: Moderno, atractivo, colores corporativos (azul y blanco), apto para Instagram.
    Incluye elementos visuales relacionados con {categoria}.
    """


def crear_prompt_para_video(titulo, categoria, resumen):
    return f"""
    Video educativo corto para TikTok/Reels.
    Título: {titulo[:80]}
    Categoría: {categoria}
    Contenido: {resumen[:200]}
    Duración: 10 segundos.
    Estilo: Dinámico, educativo, con movimiento de cámara suave.
    Texto en pantalla: "Aprende sobre {categoria}"
    """


def guardar_en_db(url, titulo, dominio, categoria, viralidad, resumen, imagen_url, video_url):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO contenido (fecha, url, titulo, dominio, categoria, viralidad, resumen, imagen_url, video_url, procesado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().isoformat(),
        url,
        titulo[:200],
        dominio,
        categoria,
        viralidad,
        resumen[:500],
        imagen_url,
        video_url,
        1
    ))
    conn.commit()
    conn.close()


def procesar_enlace_completo(url):
    print(f"\n📡 Procesando: {url[:80]}...")

    resultado = {
        "exito": False,
        "url": url,
        "error": None
    }

    try:
        contenido = leer_contenido_url(url)
        if not contenido['exito']:
            resultado['error'] = "No se pudo acceder al enlace"
            return resultado

        resultado['titulo'] = contenido['titulo']
        print(f"   📄 Título: {contenido['titulo'][:60]}...")

        categoria, viralidad = clasificar_con_gemini(
            contenido['titulo'],
            contenido['descripcion'],
            contenido['dominio']
        )
        resultado['categoria'] = categoria
        resultado['viralidad'] = viralidad
        print(f"   📁 Categoría: {categoria} (viralidad: {viralidad}/10)")

        resumen = generar_resumen_con_gemini(contenido['titulo'], contenido['descripcion'])
        resultado['resumen'] = resumen[:500]
        print(f"   📝 Resumen generado")

        prompt_imagen = crear_prompt_para_imagen(contenido['titulo'], categoria, resumen)
        prompt_video = crear_prompt_para_video(contenido['titulo'], categoria, resumen)

        resultado['imagen_url'] = generar_imagen_con_higgsfield(prompt_imagen, contenido['titulo'], categoria)
        resultado['video_url'] = generar_video_con_higgsfield(prompt_video, contenido['titulo'], categoria)

        guardar_en_db(
            url, contenido['titulo'], contenido['dominio'],
            categoria, viralidad, resumen, resultado['imagen_url'], resultado['video_url']
        )

        resultado['exito'] = True
        return resultado

    except Exception as e:
        print(f"   ❌ Error: {e}")
        resultado['error'] = str(e)
        return resultado


def procesar_enlace_completo_async(url, job_id):
    global trabajos
    try:
        resultado = procesar_enlace_completo(url)
        trabajos[job_id]["status"] = "completed"
        trabajos[job_id]["resultado"] = resultado
        print(f"✅ Trabajo {job_id} completado")
    except Exception as e:
        trabajos[job_id]["status"] = "error"
        trabajos[job_id]["error"] = str(e)
        print(f"❌ Trabajo {job_id} falló: {e}")


# ============================================
# ENDPOINTS
# ============================================

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Construex Ecosystem - Generador Automático</title>
        <style>
            body { font-family: Arial; margin: 40px; background: #f0f2f5; text-align: center; }
            .container { max-width: 800px; margin: auto; background: white; padding: 30px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            input { width: 80%; padding: 12px; margin: 10px; border: 1px solid #ddd; border-radius: 5px; }
            button { background: #27ae60; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
            button:hover { background: #229954; }
            .resultado { margin-top: 20px; padding: 15px; background: #e8f4f8; border-radius: 10px; text-align: left; display: none; }
            .loading { color: #666; }
            img, video { max-width: 100%; margin-top: 10px; border-radius: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏗️ Construex Ecosystem</h1>
            <p>Ingresa un enlace y obtendrás IMAGEN + VIDEO automáticamente</p>
            
            <input type="text" id="urlInput" placeholder="https://ejemplo.com/articulo">
            <br>
            <button onclick="procesar()">🚀 Generar Contenido</button>
            
            <div id="resultado" class="resultado"></div>
        </div>
        
        <script>
            let jobInterval = null;
            
            async function procesar() {
                const url = document.getElementById('urlInput').value;
                if (!url) { alert('Ingresa una URL'); return; }
                
                const resultadoDiv = document.getElementById('resultado');
                resultadoDiv.style.display = 'block';
                resultadoDiv.innerHTML = '<div class="loading">⏳ Procesando... Generando imagen y video (puede tomar 1-2 minutos)</div>';
                
                try {
                    const response = await fetch('/procesar', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ mensaje: url })
                    });
                    const data = await response.json();
                    
                    if (data.job_id) {
                        resultadoDiv.innerHTML = `<div class="loading">⏳ Procesando en segundo plano... ID: ${data.job_id}<br>Espera unos momentos y actualiza.</div>`;
                        
                        // Consultar estado cada 5 segundos
                        jobInterval = setInterval(async () => {
                            const estadoRes = await fetch(`/estado/${data.job_id}`);
                            const estadoData = await estadoRes.json();
                            
                            if (estadoData.status === 'completed') {
                                clearInterval(jobInterval);
                                mostrarResultado(estadoData.resultado);
                            } else if (estadoData.status === 'error') {
                                clearInterval(jobInterval);
                                resultadoDiv.innerHTML = `<strong>❌ Error:</strong> ${estadoData.error}`;
                            }
                        }, 5000);
                    } else if (data.exito) {
                        mostrarResultado(data);
                    } else {
                        resultadoDiv.innerHTML = `<strong>❌ Error:</strong> ${data.error || 'No se pudo procesar'}`;
                    }
                } catch(e) {
                    resultadoDiv.innerHTML = `<strong>❌ Error:</strong> ${e.message}`;
                }
            }
            
            function mostrarResultado(data) {
                const resultadoDiv = document.getElementById('resultado');
                let html = `<strong>✅ ¡Contenido generado!</strong><br>`;
                html += `<p><strong>📁 Categoría:</strong> ${data.categoria}</p>`;
                html += `<p><strong>🔥 Viralidad:</strong> ${data.viralidad}/10</p>`;
                html += `<p><strong>📝 Resumen:</strong> ${data.resumen || 'No disponible'}</p>`;
                
                if (data.imagen_url) {
                    html += `<hr><strong>🖼️ Imagen generada:</strong><br>`;
                    html += `<img src="${data.imagen_url}" alt="Imagen generada" style="max-width:100%; border-radius:10px;">`;
                    html += `<br><a href="${data.imagen_url}" download>📥 Descargar Imagen</a>`;
                } else {
                    html += `<hr><p>⚠️ No se pudo generar imagen</p>`;
                }
                
                if (data.video_url) {
                    html += `<hr><strong>🎬 Video generado:</strong><br>`;
                    html += `<video controls style="max-width:100%; border-radius:10px;">
                                <source src="${data.video_url}" type="video/mp4">
                                Tu navegador no soporta video.
                             </video>`;
                    html += `<br><a href="${data.video_url}" download>📥 Descargar Video</a>`;
                } else {
                    html += `<hr><p>⚠️ No se pudo generar video</p>`;
                }
                
                resultadoDiv.innerHTML = html;
                document.getElementById('urlInput').value = '';
            }
        </script>
    </body>
    </html>
    """


@app.route('/procesar', methods=['POST'])
def procesar():
    data = request.get_json()
    mensaje = data.get('mensaje', '')
    
    if not mensaje:
        return jsonify({"error": "No hay mensaje"}), 400
    enlaces = extraer_enlaces(mensaje)
    if not enlaces:
        return jsonify({"error": "No se encontraron enlaces"}), 400
    
    # Para enlaces simples, procesar directamente
    if len(enlaces) == 1:
        resultado = procesar_enlace_completo(enlaces[0])
        return jsonify(resultado), 200
    
    # Para múltiples enlaces, usar async
    job_id = str(uuid.uuid4())
    trabajos[job_id] = {"status": "processing", "resultado": None}
    
    thread = threading.Thread(target=procesar_enlace_completo_async, args=(enlaces[0], job_id))
    thread.start()
    
    return jsonify({"job_id": job_id, "status": "processing", "message": "Procesando en segundo plano"}), 202


@app.route('/estado/<job_id>', methods=['GET'])
def estado_trabajo(job_id):
    if job_id not in trabajos:
        return jsonify({"error": "Trabajo no encontrado"}), 404
    
    trabajo = trabajos[job_id]
    if trabajo["status"] == "completed":
        return jsonify({"status": "completed", "resultado": trabajo["resultado"]}), 200
    elif trabajo["status"] == "error":
        return jsonify({"status": "error", "error": trabajo["error"]}), 500
    else:
        return jsonify({"status": "processing"}), 202


@app.route('/imagenes/<path:filename>')
def descargar_imagen(filename):
    return send_from_directory(IMAGENES_DIR, filename, as_attachment=True)


@app.route('/videos/<path:filename>')
def descargar_video(filename):
    return send_from_directory(VIDEOS_DIR, filename, as_attachment=True)


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
         CONSTRUEX ECOSYSTEM - CON PROCESAMIENTO ASÍNCRONO
======================================================================

FUNCIONALIDADES:
   ✅ Extrae contenido del enlace
   ✅ Clasifica con IA (Gemini)
   ✅ Genera imagen profesional (Higgsfield)
   ✅ Genera video educativo (Higgsfield)
   ✅ Procesamiento asíncrono (sin timeout)

ACCESO: http://localhost:10000/

======================================================================
""")
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)