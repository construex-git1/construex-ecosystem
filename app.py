"""
======================================================================
         CONSTRUEX ECOSYSTEM - IMÁGENES LISTAS PARA INSTAGRAM
======================================================================
"""

import os
import re
import requests
import time
from flask import Flask, request, jsonify, send_from_directory
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import textwrap

load_dotenv()
app = Flask(__name__)

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


def generar_imagen_posteable(titulo, resumen, categoria, categoria_color):
    """
    Genera una imagen profesional para Instagram con texto superpuesto
    """
    # Dimensiones para Instagram (cuadrado)
    WIDTH, HEIGHT = 1080, 1080
    
    # Crear imagen de fondo con degradado
    img = Image.new('RGB', (WIDTH, HEIGHT), color=categoria_color)
    
    # Añadir efecto de gradiente (más profesional)
    for i in range(HEIGHT):
        alpha = int(255 * (1 - i / HEIGHT))
        overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, alpha // 4))
        img = img.convert('RGBA')
        img = Image.alpha_composite(img, overlay)
    
    draw = ImageDraw.Draw(img)
    
    # Intentar cargar fuentes (si no existen, usar la predeterminada)
    try:
        font_title = ImageFont.truetype("arial.ttf", 60)
        font_subtitle = ImageFont.truetype("arial.ttf", 40)
        font_body = ImageFont.truetype("arial.ttf", 30)
        font_footer = ImageFont.truetype("arial.ttf", 25)
    except:
        font_title = ImageFont.load_default()
        font_subtitle = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_footer = ImageFont.load_default()
    
    # 1. Categoría (arriba)
    categoria_text = f"🏗️ {categoria.upper()}"
    bbox = draw.textbbox((0, 0), categoria_text, font=font_subtitle)
    w = bbox[2] - bbox[0]
    draw.text(((WIDTH - w) // 2, 80), categoria_text, fill=(255, 255, 255), font=font_subtitle)
    
    # 2. Título principal (wrap)
    titulo_lines = textwrap.wrap(titulo, width=35)
    y_offset = 200
    for line in titulo_lines[:3]:  # Máximo 3 líneas
        bbox = draw.textbbox((0, 0), line, font=font_title)
        w = bbox[2] - bbox[0]
        draw.text(((WIDTH - w) // 2, y_offset), line, fill=(255, 255, 255), font=font_title)
        y_offset += 80
    
    # 3. Resumen
    resumen_lines = textwrap.wrap(resumen, width=45)
    y_offset = 500
    for line in resumen_lines[:6]:  # Máximo 6 líneas
        bbox = draw.textbbox((0, 0), line, font=font_body)
        w = bbox[2] - bbox[0]
        draw.text(((WIDTH - w) // 2, y_offset), line, fill=(255, 255, 240), font=font_body)
        y_offset += 45
    
    # 4. Call to Action (abajo)
    cta_text = f"✨ Aprende más en Construex ✨"
    bbox = draw.textbbox((0, 0), cta_text, font=font_footer)
    w = bbox[2] - bbox[0]
    draw.text(((WIDTH - w) // 2, HEIGHT - 100), cta_text, fill=(255, 215, 0), font=font_footer)
    
    # 5. Hashtags sugeridos
    hashtags = f"#{categoria.replace(' ', '')} #Construex #Educacion #Aprendizaje"
    bbox = draw.textbbox((0, 0), hashtags, font=font_footer)
    w = bbox[2] - bbox[0]
    draw.text(((WIDTH - w) // 2, HEIGHT - 50), hashtags, fill=(200, 200, 200), font=font_footer)
    
    # Guardar imagen
    timestamp = str(int(time.time()))
    nombre = re.sub(r'[^\w\s-]', '', titulo[:30]).replace(' ', '_')
    filename = f"instagram_{timestamp}_{nombre}.png"
    filepath = os.path.join(IMAGENES_DIR, filename)
    
    img.save(filepath, "PNG")
    print(f"   ✅ Imagen para Instagram guardada: {filepath}")
    return f"/imagenes/{filename}"


@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Construex - Generador de Imágenes para Instagram</title>
        <style>
            body { font-family: Arial; margin: 40px; background: #f0f2f5; text-align: center; }
            .container { max-width: 800px; margin: auto; background: white; padding: 30px; border-radius: 15px; }
            input { width: 80%; padding: 12px; margin: 10px; border: 1px solid #ddd; border-radius: 5px; }
            button { background: #27ae60; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
            .resultado { margin-top: 20px; padding: 15px; background: #e8f4f8; border-radius: 10px; text-align: left; display: none; }
            img { max-width: 100%; margin-top: 10px; border-radius: 10px; box-shadow: 0 5px 15px rgba(0,0,0,0.2); }
            .clasificacion { background: #d4edda; padding: 10px; border-radius: 5px; margin-bottom: 15px; }
            .preview { margin-top: 15px; text-align: center; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏗️ Construex Ecosystem</h1>
            <p>Genera imágenes listas para Instagram desde cualquier enlace</p>
            
            <input type="text" id="urlInput" placeholder="https://ejemplo.com/articulo">
            <br>
            <button onclick="procesar()">🚀 Generar Imagen para Instagram</button>
            <div id="resultado" class="resultado"></div>
        </div>
        <script>
            async function procesar() {
                const url = document.getElementById('urlInput').value;
                if (!url) { alert('Ingresa una URL'); return; }
                
                const resultadoDiv = document.getElementById('resultado');
                resultadoDiv.style.display = 'block';
                resultadoDiv.innerHTML = '<div>⏳ Procesando enlace y generando imagen...</div>';
                
                try {
                    const response = await fetch('/procesar', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ mensaje: url })
                    });
                    const data = await response.json();
                    
                    if (data.exito) {
                        let html = `<div class="clasificacion">`;
                        html += `<strong>📁 Categoría:</strong> ${data.categoria}<br>`;
                        html += `<strong>🔥 Viralidad:</strong> ${data.viralidad}/10<br>`;
                        html += `<strong>📝 Título:</strong> ${data.titulo || 'No disponible'}</div>`;
                        
                        if (data.imagen_url) {
                            html += `<div class="preview">`;
                            html += `<strong>🖼️ Imagen lista para Instagram:</strong><br>`;
                            html += `<img src="${data.imagen_url}" alt="Imagen para Instagram">`;
                            html += `<br><a href="${data.imagen_url}" download style="display: inline-block; margin-top: 10px; background: #3498db; color: white; padding: 8px 16px; border-radius: 5px; text-decoration: none;">📥 Descargar Imagen</a>`;
                            html += `</div>`;
                        }
                        
                        resultadoDiv.innerHTML = html;
                        document.getElementById('urlInput').value = '';
                    } else {
                        resultadoDiv.innerHTML = `<strong>❌ Error:</strong> ${data.error}`;
                    }
                } catch(e) {
                    resultadoDiv.innerHTML = `<strong>❌ Error:</font> ${e.message}`;
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
    
    # Generar resumen más atractivo para Instagram
    resumen = contenido['descripcion'][:300]
    
    imagen_url = generar_imagen_posteable(contenido['titulo'], resumen, categoria, color)
    
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