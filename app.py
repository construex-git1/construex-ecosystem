import os
import re
import requests
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urlparse

app = Flask(__name__)

def extraer_enlaces(texto):
    patron_url = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(patron_url, texto)

def leer_contenido_url(url):
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
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

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Construex</title></head>
    <body style="font-family:Arial; text-align:center; margin-top:50px;">
        <h1>🏗️ Construex Ecosystem</h1>
        <p>Ingresa un enlace y te diré su categoría</p>
        <input type="text" id="urlInput" style="width:60%; padding:10px;">
        <button onclick="procesar()" style="padding:10px 20px; background:#27ae60; color:white; border:none;">Analizar</button>
        <div id="resultado" style="margin-top:20px;"></div>
        <script>
            async function procesar() {
                const url = document.getElementById('urlInput').value;
                if(!url) { alert('Ingresa URL'); return; }
                document.getElementById('resultado').innerHTML = 'Procesando...';
                const response = await fetch('/procesar', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({mensaje: url})
                });
                const data = await response.json();
                document.getElementById('resultado').innerHTML = `
                    <h3>✅ Resultado</h3>
                    <p><strong>Categoría:</strong> ${data.categoria}</p>
                    <p><strong>Viralidad:</strong> ${data.viralidad}/10</p>
                    <p><strong>Título:</strong> ${data.titulo || 'No disponible'}</p>
                `;
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
    
    return jsonify({
        "exito": True,
        "categoria": categoria,
        "viralidad": viralidad,
        "titulo": contenido['titulo'],
        "url": enlaces[0]
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)