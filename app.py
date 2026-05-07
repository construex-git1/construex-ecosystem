"""
======================================================================
         CONSTRUEX ECOSYSTEM - CON POLLINATIONS COMPLETO
======================================================================
"""

import os
import re
import requests
import time
import json
from flask import Flask, request, jsonify, send_from_directory
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# Directorios
IMAGENES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imagenes_generadas")
VIDEOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "videos_generados")
TEXTOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "textos_generados")
AUDIOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audios_generados")

for d in [IMAGENES_DIR, VIDEOS_DIR, TEXTOS_DIR, AUDIOS_DIR]:
    os.makedirs(d, exist_ok=True)

# API Key de Pollinations (opcional, pero recomendada)
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY", "")
POLLINATIONS_BASE = "https://gen.pollinations.ai"


def extraer_enlaces(texto):
    patron_url = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(patron_url, texto)


def leer_contenido_url(url):
    try:
        response = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.text, 'html.parser')
        
        titulo = soup.find('title').text.strip() if soup.find('title') else "Sin título"
        
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        descripcion = meta_desc.get('content', '')[:500] if meta_desc else ""
        
        if not descripcion:
            for script in soup(["script", "style"]):
                script.decompose()
            texto = soup.get_text()
            descripcion = ' '.join(texto.split())[:500]
        
        return {"exito": True, "titulo": titulo, "descripcion": descripcion, "dominio": urlparse(url).netloc}
    except Exception as e:
        return {"exito": False, "error": str(e)}


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


# ============================================
# 1. GENERACIÓN DE IMAGEN
# ============================================

def generar_imagen(prompt, titulo):
    """Genera imagen usando Pollinations"""
    url = f"{POLLINATIONS_BASE}/v1/images/generations"
    
    headers = {"Content-Type": "application/json"}
    if POLLINATIONS_API_KEY:
        headers["Authorization"] = f"Bearer {POLLINATIONS_API_KEY}"
    
    payload = {
        "prompt": prompt,
        "width": 1080,
        "height": 1080,
        "model": "flux"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            image_url = data.get("data", [{}])[0].get("url")
            if image_url:
                timestamp = str(int(time.time()))
                nombre = re.sub(r'[^\w\s-]', '', titulo[:30]).replace(' ', '_')
                filename = f"imagen_{timestamp}_{nombre}.jpg"
                filepath = os.path.join(IMAGENES_DIR, filename)
                
                img = requests.get(image_url)
                with open(filepath, 'wb') as f:
                    f.write(img.content)
                return f"/imagenes/{filename}"
    except Exception as e:
        print(f"Error imagen: {e}")
    return None


# ============================================
# 2. GENERACIÓN DE VIDEO
# ============================================

def generar_video(prompt, titulo):
    """Genera video usando Pollinations (veo o seedance)"""
    url = f"{POLLINATIONS_BASE}/v1/video/generations"
    
    headers = {"Content-Type": "application/json"}
    if POLLINATIONS_API_KEY:
        headers["Authorization"] = f"Bearer {POLLINATIONS_API_KEY}"
    
    payload = {
        "prompt": prompt,
        "duration": 6,
        "aspect_ratio": "9:16",
        "model": "veo"
    }
    
    try:
        print("   🎬 Generando video...")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 202:
            job_id = response.json().get("id")
            print(f"   ⏳ Video en proceso (ID: {job_id})...")
            
            for i in range(60):
                time.sleep(5)
                status_resp = requests.get(f"{url}/{job_id}", headers=headers)
                status_data = status_resp.json()
                
                if status_data.get("status") == "completed":
                    video_url = status_data.get("output", {}).get("url")
                    if video_url:
                        timestamp = str(int(time.time()))
                        nombre = re.sub(r'[^\w\s-]', '', titulo[:30]).replace(' ', '_')
                        filename = f"video_{timestamp}_{nombre}.mp4"
                        filepath = os.path.join(VIDEOS_DIR, filename)
                        
                        video = requests.get(video_url)
                        with open(filepath, 'wb') as f:
                            f.write(video.content)
                        return f"/videos/{filename}"
                elif status_data.get("status") == "failed":
                    return None
            return None
    except Exception as e:
        print(f"Error video: {e}")
    return None


# ============================================
# 3. GENERACIÓN DE TEXTO / INFOGRAFÍA
# ============================================

def generar_texto(prompt):
    """Genera texto usando Pollinations (presentaciones, resúmenes, etc.)"""
    url = f"{POLLINATIONS_BASE}/v1/chat/completions"
    
    headers = {"Content-Type": "application/json"}
    if POLLINATIONS_API_KEY:
        headers["Authorization"] = f"Bearer {POLLINATIONS_API_KEY}"
    
    payload = {
        "model": "openai-fast",
        "messages": [
            {"role": "system", "content": "Eres un asistente que genera presentaciones profesionales, resúmenes ejecutivos y contenido educativo."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        print(f"Error texto: {e}")
    return None


def generar_presentacion(titulo, categoria, resumen):
    """Genera una presentación estructurada en HTML/JSON"""
    prompt = f"""
    Crea una presentación profesional sobre "{titulo}" (categoría: {categoria}).
    Contexto: {resumen[:300]}
    
    Genera el siguiente formato JSON:
    {{
        "slides": [
            {{"title": "Título de la diapositiva 1", "content": "Contenido..."}},
            {{"title": "Título de la diapositiva 2", "content": "Contenido..."}},
            ...
        ],
        "summary": "Resumen ejecutivo de 2-3 líneas"
    }}
    """
    
    texto = generar_texto(prompt)
    if texto:
        try:
            # Limpiar JSON
            if "```json" in texto:
                texto = texto.split("```json")[1].split("```")[0]
            data = json.loads(texto.strip())
            
            timestamp = str(int(time.time()))
            nombre = re.sub(r'[^\w\s-]', '', titulo[:30]).replace(' ', '_')
            filename = f"presentacion_{timestamp}_{nombre}.html"
            filepath = os.path.join(TEXTOS_DIR, filename)
            
            # Crear HTML visual
            html = f"""<!DOCTYPE html>
            <html>
            <head><title>Presentación - {titulo}</title>
            <style>
                body {{ font-family: Arial; background: #1a1a2e; color: white; margin: 0; }}
                .slide {{ min-height: 100vh; display: flex; align-items: center; justify-content: center; flex-direction: column; padding: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }}
                .slide h1 {{ font-size: 48px; margin-bottom: 20px; }}
                .slide p {{ font-size: 24px; max-width: 800px; text-align: center; line-height: 1.5; }}
                .slide-number {{ position: fixed; bottom: 20px; right: 20px; background: rgba(0,0,0,0.5); padding: 8px 16px; border-radius: 20px; }}
            </style>
            </head>
            <body>"""
            
            for i, slide in enumerate(data.get("slides", []), 1):
                html += f"""
                <div class="slide">
                    <h1>{slide.get('title', '')}</h1>
                    <p>{slide.get('content', '')}</p>
                    <div class="slide-number">{i}/{len(data.get('slides', []))}</div>
                </div>"""
            
            html += "</body></html>"
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)
            return f"/textos/{filename}"
        except:
            pass
    return None


# ============================================
# 4. GENERACIÓN DE AUDIO (PODCAST)
# ============================================

def generar_audio(texto, titulo):
    """Genera audio usando Pollinations (text-to-speech)"""
    url = f"{POLLINATIONS_BASE}/v1/audio/speech"
    
    headers = {"Content-Type": "application/json"}
    if POLLINATIONS_API_KEY:
        headers["Authorization"] = f"Bearer {POLLINATIONS_API_KEY}"
    
    payload = {
        "model": "tts-1",
        "input": texto[:500],
        "voice": "alloy",
        "speed": 1.0
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            timestamp = str(int(time.time()))
            nombre = re.sub(r'[^\w\s-]', '', titulo[:30]).replace(' ', '_')
            filename = f"audio_{timestamp}_{nombre}.mp3"
            filepath = os.path.join(AUDIOS_DIR, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return f"/audios/{filename}"
    except Exception as e:
        print(f"Error audio: {e}")
    return None


def generar_podcast(titulo, resumen, categoria):
    """Genera un podcast completo (texto + audio)"""
    prompt = f"""
    Genera un guion para podcast educativo sobre {categoria}: "{titulo}".
    
    Contenido: {resumen[:500]}
    
    Formato:
    - Intro (30 segundos)
    - Desarrollo (2-3 minutos)
    - Conclusión (30 segundos)
    """
    
    guion = generar_texto(prompt)
    if guion:
        return generar_audio(guion, titulo)
    return None


# ============================================
# ENDPOINT PRINCIPAL
# ============================================

@app.route('/procesar', methods=['POST'])
def procesar():
    data = request.get_json()
    mensaje = data.get('mensaje', '')
    
    opciones = {
        'imagen': data.get('generar_imagen', True),
        'video': data.get('generar_video', False),
        'presentacion': data.get('generar_presentacion', False),
        'podcast': data.get('generar_podcast', False)
    }
    
    if not mensaje:
        return jsonify({"error": "No hay mensaje"}), 400
    
    enlaces = extraer_enlaces(mensaje)
    if not enlaces:
        return jsonify({"error": "No se encontraron enlaces"}), 400
    
    contenido = leer_contenido_url(enlaces[0])
    if not contenido['exito']:
        return jsonify({"error": contenido.get('error', 'No se pudo acceder')}), 400
    
    categoria, viralidad = clasificar_manual(contenido['titulo'], contenido['descripcion'], contenido['dominio'])
    
    # Generar resumen para usar en otros formatos
    resumen = contenido['descripcion'][:500]
    
    resultado = {
        "exito": True,
        "categoria": categoria,
        "viralidad": viralidad,
        "titulo": contenido['titulo'],
        "url": enlaces[0]
    }
    
    # Generar según opciones
    if opciones.get('imagen'):
        prompt = f"Imagen profesional sobre {categoria}: {contenido['titulo'][:150]}. Estilo moderno."
        imagen = generar_imagen(prompt, contenido['titulo'])
        if imagen:
            resultado["imagen_url"] = imagen
    
    if opciones.get('video'):
        prompt = f"Video educativo corto sobre {categoria}: {contenido['titulo'][:150]}"
        video = generar_video(prompt, contenido['titulo'])
        if video:
            resultado["video_url"] = video
    
    if opciones.get('presentacion'):
        presentacion = generar_presentacion(contenido['titulo'], categoria, resumen)
        if presentacion:
            resultado["presentacion_url"] = presentacion
    
    if opciones.get('podcast'):
        podcast = generar_podcast(contenido['titulo'], resumen, categoria)
        if podcast:
            resultado["podcast_url"] = podcast
    
    return jsonify(resultado), 200


# ============================================
# ENDPOINTS DE DESCARGA
# ============================================

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Construex Ecosystem</title>
        <style>
            body { font-family: Arial; margin: 40px; background: #f0f2f5; text-align: center; }
            .container { max-width: 800px; margin: auto; background: white; padding: 30px; border-radius: 15px; }
            input, select { width: 80%; padding: 12px; margin: 10px; border: 1px solid #ddd; border-radius: 5px; }
            button { background: #27ae60; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; }
            .checkbox-group { display: flex; gap: 15px; justify-content: center; margin: 15px 0; flex-wrap: wrap; }
            .resultado { margin-top: 20px; padding: 15px; background: #e8f4f8; border-radius: 10px; text-align: left; display: none; }
            img { max-width: 100%; margin-top: 10px; border-radius: 10px; }
            video { max-width: 100%; margin-top: 10px; border-radius: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏗️ Construex Ecosystem</h1>
            <p>Genera imagen, video, presentación y podcast desde cualquier enlace</p>
            
            <input type="text" id="urlInput" placeholder="https://ejemplo.com/articulo">
            
            <div class="checkbox-group">
                <label><input type="checkbox" id="imgCheck" checked> 🖼️ Imagen</label>
                <label><input type="checkbox" id="videoCheck"> 🎬 Video</label>
                <label><input type="checkbox" id="presCheck"> 📊 Presentación</label>
                <label><input type="checkbox" id="podCheck"> 🎙️ Podcast</label>
            </div>
            
            <button onclick="procesar()">🚀 Generar Contenido</button>
            <div id="resultado" class="resultado"></div>
        </div>
        <script>
            async function procesar() {
                const url = document.getElementById('urlInput').value;
                if (!url) { alert('Ingresa una URL'); return; }
                
                const resultadoDiv = document.getElementById('resultado');
                resultadoDiv.style.display = 'block';
                resultadoDiv.innerHTML = '<div>⏳ Procesando...</div>';
                
                const body = {
                    mensaje: url,
                    generar_imagen: document.getElementById('imgCheck').checked,
                    generar_video: document.getElementById('videoCheck').checked,
                    generar_presentacion: document.getElementById('presCheck').checked,
                    generar_podcast: document.getElementById('podCheck').checked
                };
                
                try {
                    const response = await fetch('/procesar', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(body)
                    });
                    const data = await response.json();
                    
                    if (data.exito) {
                        let html = `<strong>✅ ¡Contenido generado!</strong><br>`;
                        html += `<p><strong>📁 Categoría:</strong> ${data.categoria}</p>`;
                        html += `<p><strong>🔥 Viralidad:</strong> ${data.viralidad}/10</p>`;
                        
                        if (data.imagen_url) html += `<hr><strong>🖼️ Imagen:</strong><br><img src="${data.imagen_url}"><br><a href="${data.imagen_url}" download>📥 Descargar</a>`;
                        if (data.video_url) html += `<hr><strong>🎬 Video:</strong><br><video controls><source src="${data.video_url}"></video><br><a href="${data.video_url}" download>📥 Descargar</a>`;
                        if (data.presentacion_url) html += `<hr><strong>📊 Presentación:</strong><br><a href="${data.presentacion_url}" target="_blank">📥 Ver/Descargar</a>`;
                        if (data.podcast_url) html += `<hr><strong>🎙️ Podcast:</strong><br><a href="${data.podcast_url}" download>📥 Descargar Audio</a>`;
                        
                        resultadoDiv.innerHTML = html;
                    } else {
                        resultadoDiv.innerHTML = `<strong>❌ Error:</strong> ${data.error}`;
                    }
                } catch(e) {
                    resultadoDiv.innerHTML = `<strong>❌ Error:</strong> ${e.message}`;
                }
            }
        </script>
    </body>
    </html>
    """


@app.route('/imagenes/<path:filename>')
def descargar_imagen(filename):
    return send_from_directory(IMAGENES_DIR, filename, as_attachment=True)


@app.route('/videos/<path:filename>')
def descargar_video(filename):
    return send_from_directory(VIDEOS_DIR, filename, as_attachment=True)


@app.route('/textos/<path:filename>')
def descargar_texto(filename):
    return send_from_directory(TEXTOS_DIR, filename, as_attachment=True)


@app.route('/audios/<path:filename>')
def descargar_audio(filename):
    return send_from_directory(AUDIOS_DIR, filename, as_attachment=True)


@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode and token and token == "construex_verify_2026":
        return challenge, 200
    return 'Forbidden', 403


@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok", "message": "Sistema Construex funcionando"})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Servidor corriendo en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)