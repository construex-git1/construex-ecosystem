"""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN ESTABLE
======================================================================
"""

import os
import re
import requests
import json
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)


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
        
        return {"exito": True, "titulo": titulo, "descripcion": descripcion}
    except Exception as e:
        return {"exito": False, "error": str(e)}


def clasificar_categoria(titulo, descripcion):
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


def generar_texto_instagram(titulo, descripcion, categoria):
    emojis = {"Construccion": "🏗️", "Emprendimiento": "🚀", "Construex University": "🎓", "Salud": "💪", "Automejora": "🌟"}
    emoji = emojis.get(categoria, "📚")
    
    return f"""{emoji} {titulo[:70]} {emoji}

📌 {descripcion[:350]}

💾 GUARDA este post
👥 COMPARTE con alguien

#{categoria.replace(' ', '')} #Construex #Noticias"""


@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Construex - Generador de Contenido</title>
        <style>
            body { font-family: Arial; background: #0f0f0f; padding: 20px; text-align: center; }
            .container { max-width: 800px; margin: auto; background: #1a1a2e; padding: 30px; border-radius: 20px; }
            input { width: 80%; padding: 12px; margin: 10px; background: #2a2a3e; border: 1px solid #3a3a4e; border-radius: 8px; color: white; }
            button { background: #27ae60; color: white; padding: 12px 30px; border: none; border-radius: 8px; cursor: pointer; }
            .resultado { margin-top: 20px; padding: 15px; background: #2a2a3e; border-radius: 10px; color: white; text-align: left; display: none; }
            textarea { width: 100%; background: #2a2a3e; color: white; border: none; padding: 10px; border-radius: 8px; }
            .copy-btn { background: #3498db; padding: 8px 16px; border: none; border-radius: 8px; color: white; cursor: pointer; margin-top: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏗️ Construex Ecosystem</h1>
            <p>Genera contenido listo para Instagram desde cualquier enlace</p>
            <input type="text" id="urlInput" placeholder="https://ejemplo.com/noticia">
            <button onclick="procesar()">🚀 Generar</button>
            <div id="resultado" class="resultado"></div>
        </div>
        <script>
        async function procesar() {
            const url = document.getElementById('urlInput').value;
            if (!url) { alert('Ingresa una URL'); return; }
            document.getElementById('resultado').style.display = 'block';
            document.getElementById('resultado').innerHTML = '<div>⏳ Procesando...</div>';
            try {
                const response = await fetch('/procesar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                const data = await response.json();
                if (data.exito) {
                    let html = `<strong>📁 Categoría:</strong> ${data.categoria}<br>`;
                    html += `<strong>🔥 Viralidad:</strong> ${data.viralidad}/10<br>`;
                    html += `<strong>📝 Título:</strong> ${data.titulo}<br><br>`;
                    html += `<textarea id="textoInstagram" rows="10" readonly>${data.texto_instagram}</textarea>`;
                    html += `<button class="copy-btn" onclick="copiarTexto()">📋 Copiar para Instagram</button>`;
                    document.getElementById('resultado').innerHTML = html;
                } else {
                    document.getElementById('resultado').innerHTML = `<strong>❌ Error:</strong> ${data.error}`;
                }
            } catch(e) {
                document.getElementById('resultado').innerHTML = `<strong>❌ Error:</strong> ${e.message}`;
            }
        }
        function copiarTexto() {
            const textarea = document.getElementById('textoInstagram');
            textarea.select();
            document.execCommand('copy');
            alert('✅ Texto copiado');
        }
        </script>
    </body>
    </html>
    """


@app.route('/procesar', methods=['POST'])
def procesar():
    data = request.get_json()
    url = data.get('url', '')
    
    if not url:
        return jsonify({"error": "No hay URL"}), 400
    
    contenido = leer_contenido_url(url)
    if not contenido['exito']:
        return jsonify({"error": contenido.get('error', 'No se pudo acceder')}), 400
    
    categoria, viralidad = clasificar_categoria(contenido['titulo'], contenido['descripcion'])
    
    texto_instagram = generar_texto_instagram(contenido['titulo'], contenido['descripcion'], categoria)
    
    return jsonify({
        "exito": True,
        "categoria": categoria,
        "viralidad": viralidad,
        "titulo": contenido['titulo'],
        "texto_instagram": texto_instagram
    })


@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)