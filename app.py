"""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN FUNCIONAL
======================================================================
"""

import os
import re
import requests
import time
import random
from flask import Flask, request, jsonify, send_from_directory
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv

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
        return "Construccion", 8
    elif any(p in texto for p in ["negocio", "emprend", "empresa", "ventas", "inversion"]):
        return "Emprendimiento", 7
    elif any(p in texto for p in ["curso", "aprender", "educacion", "certificacion"]):
        return "Construex University", 6
    elif any(p in texto for p in ["salud", "medico", "bienestar", "dieta"]):
        return "Salud", 6
    return "Automejora", 5


def generar_imagen(titulo, categoria):
    """Genera imagen usando Pollinations (funciona)"""
    prompt = f"{categoria}: {titulo[:100]}"
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=1080&height=1080&nologo=true"
    
    timestamp = str(int(time.time()))
    nombre = re.sub(r'[^\w\s-]', '', titulo[:30]).replace(' ', '_')
    filename = f"imagen_{timestamp}_{nombre}.jpg"
    filepath = os.path.join(IMAGENES_DIR, filename)
    
    try:
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return f"/imagenes/{filename}"
    except Exception as e:
        print(f"Error imagen: {e}")
    return None


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
            input { width: 80%; padding: 12px; margin: 10px; border: 1px solid #ddd; border-radius: 5px; }
            button { background: #27ae60; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; }
            .resultado { margin-top: 20px; padding: 15px; background: #e8f4f8; border-radius: 10px; text-align: left; display: none; }
            img { max-width: 100%; margin-top: 10px; border-radius: 10px; }
            .clasificacion { background: #d4edda; padding: 10px; border-radius: 5px; margin-bottom: 15px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏗️ Construex Ecosystem</h1>
            <p>Clasifica contenido + genera imagen automática</p>
            
            <input type="text" id="urlInput" placeholder="https://ejemplo.com/articulo">
            <br>
            <button onclick="procesar()">🚀 Generar</button>
            <div id="resultado" class="resultado"></div>
        </div>
        <script>
            async function procesar() {
                const url = document.getElementById('urlInput').value;
                if (!url) { alert('Ingresa una URL'); return; }
                
                const resultadoDiv = document.getElementById('resultado');
                resultadoDiv.style.display = 'block';
                resultadoDiv.innerHTML = '<div>⏳ Procesando... (30-60 segundos)</div>';
                
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
                        html += `<strong>📝 Título:</strong> ${data.titulo || 'No disponible'}<br>`;
                        html += `<strong>📄 Resumen:</strong> ${data.resumen || 'No disponible'}</div>`;
                        
                        if (data.imagen_url) {
                            html += `<hr><strong>🖼️ Imagen generada:</strong><br>`;
                            html += `<img src="${data.imagen_url}" alt="Imagen generada">`;
                            html += `<br><a href="${data.imagen_url}" download>📥 Descargar Imagen</a>`;
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
    
    categoria, viralidad = clasificar_manual(contenido['titulo'], contenido['descripcion'], contenido['dominio'])
    
    imagen_url = generar_imagen(contenido['titulo'], categoria)
    
    return jsonify({
        "exito": True,
        "categoria": categoria,
        "viralidad": viralidad,
        "titulo": contenido['titulo'],
        "resumen": contenido['descripcion'][:300],
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