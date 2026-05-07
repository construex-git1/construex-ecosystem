"""
======================================================================
         CONSTRUEX ECOSYSTEM - CON CLOUDINARY
======================================================================
"""

import os
import re
import requests
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from flask import Flask, request, jsonify, send_from_directory
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# ============================================
# CONFIGURACION DE CLOUDINARY
# ============================================

cloudinary.config(
    cloud_name="dcjggdlla",
    api_key="519915375639214",
    api_secret="0HCTwBlLe1wPHFsyLp02N_k8jHo"
)

# Directorios
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
    if any(p in texto for p in ["construc", "centro comercial", "mall", "obra", "empleo", "edificio", "canal"]):
        return "Construccion", 8, "#795548"
    elif any(p in texto for p in ["negocio", "emprend", "empresa", "ventas", "inversion"]):
        return "Emprendimiento", 7, "#FF9800"
    elif any(p in texto for p in ["curso", "aprender", "educacion", "certificacion"]):
        return "Construex University", 6, "#2196F3"
    elif any(p in texto for p in ["salud", "medico", "bienestar", "dieta"]):
        return "Salud", 6, "#4CAF50"
    return "Automejora", 5, "#9C27B0"


def generar_imagen_cloudinary(titulo, resumen, categoria, color):
    """Genera imagen profesional con Cloudinary"""
    
    # Limpiar texto para URL
    titulo_clean = titulo[:60].replace(' ', '%20').replace('&', '%26')
    resumen_clean = resumen[:200].replace(' ', '%20').replace('&', '%26')
    
    # Construir URL de Cloudinary con texto superpuesto
    # Fondo con gradiente según categoría
    base_url = "https://res.cloudinary.com/dcjggdlla/image/upload/v1/"
    
    # Crear overlay de texto para el título
    overlay_title = f"l_text:Arial_60_bold:{titulo_clean},g_north_west,x_50,y_150,co_rgb:FFFFFF"
    
    # Overlay para el resumen
    overlay_summary = f"l_text:Arial_30:{resumen_clean},g_north_west,x_50,y_300,co_rgb:FFFFFF,co_alpha:80"
    
    # Overlay para la categoría
    overlay_category = f"l_text:Arial_40_bold:{categoria.upper()},g_north_west,x_50,y_80,co_rgb:FFD700"
    
    # Overlay para el CTA
    overlay_cta = f"l_text:Arial_30:✨%20Aprende%20más%20en%20Construex%20✨,g_south_west,x_50,y_80,co_rgb:FFD700"
    
    # Overlay para hashtags
    overlay_hashtags = f"l_text:Arial_25:%23{categoria}%20%23Construex%20%23Educacion, g_south_west,x_50,y_40,co_rgb:AAAAAA"
    
    # Construir URL final
    url = f"{base_url}w_1080,h_1080,c_fill,g_center/bo_5px_solid_rgb:{color[1:]}/{overlay_category}/{overlay_title}/{overlay_summary}/{overlay_cta}/{overlay_hashtags}/bg_{color[1:]}/v1/construex_template"
    
    # Descargar la imagen generada
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            import time
            timestamp = str(int(time.time()))
            nombre = re.sub(r'[^\w\s-]', '', titulo[:30]).replace(' ', '_')
            filename = f"instagram_{timestamp}_{nombre}.jpg"
            filepath = os.path.join(IMAGENES_DIR, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return f"/imagenes/{filename}"
    except Exception as e:
        print(f"Error generando imagen: {e}")
    
    return None


@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Construex - Generador de Imágenes</title>
        <style>
            body { font-family: Arial; margin: 40px; background: #f0f2f5; text-align: center; }
            .container { max-width: 800px; margin: auto; background: white; padding: 30px; border-radius: 15px; }
            input { width: 80%; padding: 12px; margin: 10px; border: 1px solid #ddd; border-radius: 5px; }
            button { background: #27ae60; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
            .resultado { margin-top: 20px; padding: 15px; background: #e8f4f8; border-radius: 10px; text-align: left; display: none; }
            img { max-width: 100%; margin-top: 10px; border-radius: 10px; box-shadow: 0 5px 15px rgba(0,0,0,0.2); }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏗️ Construex Ecosystem</h1>
            <p>Genera imágenes profesionales listas para Instagram</p>
            
            <input type="text" id="urlInput" placeholder="https://ejemplo.com/articulo">
            <br>
            <button onclick="procesar()">🚀 Generar Imagen</button>
            <div id="resultado" class="resultado"></div>
        </div>
        <script>
            async function procesar() {
                const url = document.getElementById('urlInput').value;
                if (!url) { alert('Ingresa una URL'); return; }
                
                const resultadoDiv = document.getElementById('resultado');
                resultadoDiv.style.display = 'block';
                resultadoDiv.innerHTML = '<div>⏳ Procesando... Generando imagen profesional</div>';
                
                try {
                    const response = await fetch('/procesar', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ mensaje: url })
                    });
                    const data = await response.json();
                    
                    if (data.exito) {
                        let html = `<div style="background:#d4edda; padding:10px; border-radius:5px; margin-bottom:15px;">`;
                        html += `<strong>📁 Categoría:</strong> ${data.categoria}<br>`;
                        html += `<strong>🔥 Viralidad:</strong> ${data.viralidad}/10<br>`;
                        html += `<strong>📝 Título:</strong> ${data.titulo}</div>`;
                        
                        if (data.imagen_url) {
                            html += `<strong>🖼️ Imagen lista para Instagram:</strong><br>`;
                            html += `<img src="${data.imagen_url}" alt="Imagen para Instagram">`;
                            html += `<br><a href="${data.imagen_url}" download style="display: inline-block; margin-top: 10px; background: #3498db; color: white; padding: 8px 16px; border-radius: 5px; text-decoration: none;">📥 Descargar Imagen</a>`;
                        }
                        
                        resultadoDiv.innerHTML = html;
                        document.getElementById('urlInput').value = '';
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


@app.route('/procesar', methods=['POST'])
def procesar():
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
    
    categoria, viralidad, color = clasificar_manual(contenido['titulo'], contenido['descripcion'], contenido['dominio'])
    
    # Limitar resumen para la imagen
    resumen = contenido['descripcion'][:250]
    
    imagen_url = generar_imagen_cloudinary(contenido['titulo'], resumen, categoria, color)
    
    return jsonify({
        "exito": True,
        "categoria": categoria,
        "viralidad": viralidad,
        "titulo": contenido['titulo'],
        "resumen": resumen,
        "imagen_url": imagen_url
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