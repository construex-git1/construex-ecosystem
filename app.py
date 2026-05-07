"""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN PROFESIONAL COMPLETA
======================================================================
"""

import os
import re
import requests
import json
import time
from flask import Flask, request, jsonify, send_from_directory
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
app = Flask(__name__)

# ============================================
# CONFIGURACION
# ============================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')

IMAGENES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imagenes_generadas")
os.makedirs(IMAGENES_DIR, exist_ok=True)


def extraer_enlaces(texto):
    patron_url = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(patron_url, texto)


def leer_contenido_url(url):
    try:
        response = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.text, 'html.parser')
        
        titulo = soup.find('title').text.strip() if soup.find('title') else "Sin título"
        
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        descripcion = meta_desc.get('content', '')[:800] if meta_desc else ""
        
        if not descripcion:
            for script in soup(["script", "style"]):
                script.decompose()
            texto = soup.get_text()
            descripcion = ' '.join(texto.split())[:800]
        
        return {"exito": True, "titulo": titulo, "descripcion": descripcion, "dominio": urlparse(url).netloc}
    except Exception as e:
        return {"exito": False, "error": str(e)}


def generar_contenido_profesional_con_gemini(titulo, descripcion, categoria):
    """Genera contenido profesional usando Gemini"""
    
    prompt = f"""
    Eres un copywriter experto en marketing de contenidos para Instagram y Facebook.
    
    Basado en este artículo, genera contenido profesional y viral:
    
    TÍTULO: {titulo}
    CATEGORÍA: {categoria}
    CONTENIDO: {descripcion[:800]}
    
    Genera EXACTAMENTE este formato JSON:
    {{
        "titulo_viral": "título corto y llamativo (máx 70 caracteres)",
        "resumen_ejecutivo": "resumen del artículo en 2-3 líneas que enganche",
        "palabras_clave": ["palabra1", "palabra2", "palabra3", "palabra4", "palabra5"],
        "descripcion_instagram": "texto para Instagram (máx 2200 caracteres) con emojis, estructura clara y call to action",
        "descripcion_facebook": "texto para Facebook (máx 2000 caracteres) más profesional",
        "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5", "#hashtag6", "#hashtag7", "#hashtag8", "#hashtag9", "#hashtag10"],
        "call_to_action": "frase que invite a comentar, guardar o compartir"
    }}
    """
    
    try:
        respuesta = gemini_model.generate_content(prompt)
        texto = respuesta.text
        if "```json" in texto:
            texto = texto.split("```json")[1].split("```")[0]
        return json.loads(texto.strip())
    except Exception as e:
        print(f"Error Gemini: {e}")
        return generar_contenido_fallback(titulo, descripcion, categoria)


def generar_contenido_fallback(titulo, descripcion, categoria):
    """Contenido de respaldo si Gemini falla"""
    titulo_corto = titulo[:65] if len(titulo) > 65 else titulo
    descripcion_corta = descripcion[:300] if len(descripcion) > 300 else descripcion
    
    emojis_categoria = {
        "Construccion": "🏗️",
        "Emprendimiento": "🚀",
        "Construex University": "🎓",
        "Salud": "💪",
        "Automejora": "🌟"
    }
    emoji = emojis_categoria.get(categoria, "📚")
    
    return {
        "titulo_viral": f"{emoji} {titulo_corto} {emoji}",
        "resumen_ejecutivo": descripcion_corta,
        "palabras_clave": [categoria, "educacion", "aprendizaje", "conocimiento", "tips"],
        "descripcion_instagram": f"{emoji} {titulo_corto}\n\n{descripcion_corta}\n\n💾 GUARDA este post para después\n👥 COMPARTE con alguien que debería saber esto\n\n{categoria} #Construex #Educacion",
        "descripcion_facebook": f"{titulo_corto}\n\n{descripcion_corta}\n\n📌 ¿Qué opinas? Déjanos tu comentario.",
        "hashtags": [f"#{categoria.replace(' ', '')}", "#Construex", "#Educacion", "#Aprende", "#Tips", "#Conocimiento", "#Desarrollo", "#Crecimiento", "#Liderazgo", "#Innovacion"],
        "call_to_action": "✨ Guarda este post y compártelo con alguien que le pueda interesar ✨"
    }


def generar_imagen_perchance(titulo, categoria, palabras_clave):
    """Genera imagen profesional usando Perchance (gratis, sin tarjeta)"""
    
    # Construir prompt rico y específico
    prompt = f"""Professional social media post image for {categoria} category. Topic: {titulo[:100]}. Keywords: {', '.join(palabras_clave[:3])}. Style: modern, clean, professional, eye-catching, suitable for Instagram and Facebook. High quality, 4K, cinematic lighting, vibrant colors. Include subtle geometric patterns or abstract shapes in the background. Do not include text or watermarks."""
    
    # Usar Perchance Image Generator (gratis, sin API key)
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=1080&height=1080&nologo=true"
    
    try:
        print(f"   🖼️ Generando imagen profesional...")
        response = requests.get(url, timeout=60)
        
        if response.status_code == 200:
            timestamp = str(int(time.time()))
            nombre = re.sub(r'[^\w\s-]', '', titulo[:30]).replace(' ', '_')
            filename = f"profesional_{timestamp}_{nombre}.png"
            filepath = os.path.join(IMAGENES_DIR, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            print(f"   ✅ Imagen guardada: {filepath}")
            return f"/imagenes/{filename}"
        else:
            print(f"   ❌ Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


def clasificar_categoria(titulo, descripcion):
    texto = f"{titulo} {descripcion}".lower()
    if any(p in texto for p in ["construc", "centro comercial", "mall", "obra", "edificio", "canal"]):
        return "Construccion"
    elif any(p in texto for p in ["negocio", "emprend", "empresa", "ventas", "inversion"]):
        return "Emprendimiento"
    elif any(p in texto for p in ["curso", "aprender", "educacion", "certificacion"]):
        return "Construex University"
    elif any(p in texto for p in ["salud", "medico", "bienestar", "dieta"]):
        return "Salud"
    return "Automejora"


@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Construex Pro - Generador Profesional</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f0f0f; min-height: 100vh; padding: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 20px; padding: 30px; margin-bottom: 30px; color: white; }
            .header h1 { font-size: 36px; margin-bottom: 10px; }
            .input-area { background: #1a1a2e; border-radius: 20px; padding: 25px; margin-bottom: 30px; }
            input { width: 100%; padding: 15px; background: #2a2a3e; border: 1px solid #3a3a4e; border-radius: 12px; color: white; font-size: 16px; margin-bottom: 15px; }
            button { background: linear-gradient(135deg, #FF6B6B, #FF8E53); color: white; padding: 15px 30px; border: none; border-radius: 12px; font-size: 16px; font-weight: bold; cursor: pointer; transition: transform 0.2s; }
            button:hover { transform: scale(1.02); }
            .loading { text-align: center; padding: 40px; color: #aaa; display: none; }
            .resultado { display: none; margin-top: 20px; }
            .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            .card { background: #1a1a2e; border-radius: 16px; overflow: hidden; }
            .card-header { background: #2a2a3e; padding: 15px 20px; color: white; font-weight: bold; }
            .card-body { padding: 20px; color: #ddd; line-height: 1.6; }
            .preview-img { width: 100%; border-radius: 12px; margin-top: 10px; }
            .copy-btn { background: #3498db; padding: 8px 16px; font-size: 14px; margin-top: 10px; cursor: pointer; border: none; border-radius: 8px; color: white; }
            .hashtag { display: inline-block; background: #2a2a3e; padding: 5px 12px; border-radius: 20px; margin: 5px; font-size: 12px; }
            .categoria-badge { display: inline-block; padding: 5px 15px; border-radius: 20px; font-size: 12px; margin-bottom: 10px; }
            textarea { width: 100%; padding: 12px; background: #2a2a3e; border: 1px solid #3a3a4e; border-radius: 8px; color: white; font-family: monospace; font-size: 13px; resize: vertical; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏗️ Construex Pro</h1>
                <p>Generador profesional de contenido para Instagram y Facebook</p>
            </div>
            
            <div class="input-area">
                <input type="text" id="urlInput" placeholder="https://ejemplo.com/articulo">
                <button onclick="generarContenido()">🚀 Generar Contenido Profesional</button>
                <div class="loading" id="loading">⏳ Analizando y generando contenido profesional...</div>
            </div>
            
            <div id="resultado" class="resultado"></div>
        </div>
        
        <script>
        async function generarContenido() {
            const url = document.getElementById('urlInput').value;
            if (!url) { alert('Ingresa una URL'); return; }
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('resultado').style.display = 'none';
            
            try {
                const response = await fetch('/generar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mensaje: url })
                });
                const data = await response.json();
                
                if (data.exito) {
                    mostrarResultado(data);
                } else {
                    alert('Error: ' + data.error);
                }
            } catch(e) {
                alert('Error: ' + e.message);
            } finally {
                document.getElementById('loading').style.display = 'none';
            }
        }
        
        function mostrarResultado(data) {
            const viral = data.contenido_viral;
            
            let html = `
                <div class="grid-2">
                    <div class="card">
                        <div class="card-header">🖼️ IMAGEN PARA PUBLICACIÓN</div>
                        <div class="card-body">
                            <img src="${data.imagen_url}?t=${Date.now()}" class="preview-img" alt="Imagen generada">
                            <a href="${data.imagen_url}" download style="display: inline-block; margin-top: 10px; background: #27ae60; color: white; padding: 8px 16px; border-radius: 8px; text-decoration: none;">📥 Descargar Imagen</a>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">📋 INFORMACIÓN DEL ARTÍCULO</div>
                        <div class="card-body">
                            <span class="categoria-badge" style="background: #9C27B0;">📁 ${data.categoria}</span>
                            <span class="categoria-badge" style="background: #e67e22;">🔥 Viralidad: ${data.viralidad}/10</span>
                            <h3 style="margin: 15px 0; color: white;">${viral.titulo_viral}</h3>
                            <p><strong>📝 Resumen Ejecutivo:</strong></p>
                            <p>${viral.resumen_ejecutivo}</p>
                            <p><strong>🔑 Palabras Clave:</strong></p>
                            <div>${viral.palabras_clave.map(k => `<span class="hashtag">${k}</span>`).join('')}</div>
                        </div>
                    </div>
                </div>
                
                <div class="card" style="margin-top: 20px;">
                    <div class="card-header">📱 TEXTO PARA INSTAGRAM</div>
                    <div class="card-body">
                        <textarea id="textoInstagram" rows="8" readonly style="width:100%;">${viral.descripcion_instagram}</textarea>
                        <button class="copy-btn" onclick="copiarTexto('textoInstagram')">📋 Copiar texto de Instagram</button>
                    </div>
                </div>
                
                <div class="card" style="margin-top: 20px;">
                    <div class="card-header">📘 TEXTO PARA FACEBOOK</div>
                    <div class="card-body">
                        <textarea id="textoFacebook" rows="6" readonly style="width:100%;">${viral.descripcion_facebook}</textarea>
                        <button class="copy-btn" onclick="copiarTexto('textoFacebook')">📋 Copiar texto de Facebook</button>
                    </div>
                </div>
                
                <div class="card" style="margin-top: 20px;">
                    <div class="card-header">🏷️ HASHTAGS</div>
                    <div class="card-body">
                        <textarea id="hashtags" rows="3" readonly style="width:100%;">${viral.hashtags.join(' ')}</textarea>
                        <button class="copy-btn" onclick="copiarTexto('hashtags')">📋 Copiar Hashtags</button>
                    </div>
                </div>
                
                <div class="card" style="margin-top: 20px; background: linear-gradient(135deg, #FFD700, #FF8C00);">
                    <div class="card-header" style="background: rgba(0,0,0,0.2);">💡 CALL TO ACTION</div>
                    <div class="card-body">
                        <p style="font-size: 18px; font-weight: bold;">${viral.call_to_action}</p>
                    </div>
                </div>
            `;
            
            document.getElementById('resultado').innerHTML = html;
            document.getElementById('resultado').style.display = 'block';
        }
        
        function copiarTexto(id) {
            const textarea = document.getElementById(id);
            textarea.select();
            document.execCommand('copy');
            alert('✅ Texto copiado al portapapeles');
        }
        </script>
    </body>
    </html>
    """


@app.route('/generar', methods=['POST'])
def generar():
    data = request.get_json()
    mensaje = data.get('mensaje', '')
    
    if not mensaje:
        return jsonify({"error": "No hay mensaje"}), 400
    
    enlaces = extraer_enlaces(mensaje)
    if not enlaces:
        return jsonify({"error": "No se encontraron enlaces"}), 400
    
    contenido = leer_contenido_url(enlaces[0])
    if not contenido['exito']:
        return jsonify({"error": contenido.get('error', 'No se pudo acceder')}), 400
    
    categoria = clasificar_categoria(contenido['titulo'], contenido['descripcion'])
    
    viralidad = {"Construccion": 8, "Emprendimiento": 7, "Construex University": 6, "Salud": 6, "Automejora": 5}.get(categoria, 5)
    
    # Generar contenido profesional con Gemini
    if GEMINI_API_KEY:
        contenido_viral = generar_contenido_profesional_con_gemini(contenido['titulo'], contenido['descripcion'], categoria)
    else:
        contenido_viral = generar_contenido_fallback(contenido['titulo'], contenido['descripcion'], categoria)
    
    # Generar imagen profesional
    imagen_url = generar_imagen_perchance(contenido['titulo'], categoria, contenido_viral['palabras_clave'])
    
    return jsonify({
        "exito": True,
        "categoria": categoria,
        "viralidad": viralidad,
        "titulo": contenido['titulo'],
        "imagen_url": imagen_url,
        "contenido_viral": contenido_viral
    })


@app.route('/imagenes/<path:filename>')
def descargar_imagen(filename):
    return send_from_directory(IMAGENES_DIR, filename, as_attachment=True)


@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok", "message": "Sistema Construex funcionando"})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Servidor corriendo en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)