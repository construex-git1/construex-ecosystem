"""
======================================================================
         CONSTRUEX ECOSYSTEM - IMÁGENES CON CANVAS
======================================================================
"""

import os
import re
import requests
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
    if any(p in texto for p in ["construc", "centro comercial", "mall", "obra", "empleo", "edificio"]):
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
    <head>
        <title>Construex - Generador de Imágenes</title>
        <style>
            body { font-family: Arial; margin: 40px; background: #f0f2f5; text-align: center; }
            .container { max-width: 900px; margin: auto; background: white; padding: 30px; border-radius: 15px; }
            input { width: 80%; padding: 12px; margin: 10px; border: 1px solid #ddd; border-radius: 5px; }
            button { background: #27ae60; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
            .resultado { margin-top: 20px; padding: 15px; background: #e8f4f8; border-radius: 10px; text-align: left; display: none; }
            canvas { max-width: 100%; border-radius: 10px; box-shadow: 0 5px 15px rgba(0,0,0,0.2); margin-top: 20px; }
            .descargar { background: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin-top: 10px; display: inline-block; text-decoration: none; }
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
        
        <canvas id="imageCanvas" style="display:none;"></canvas>
        
        <script>
        const colores = {
            "Construccion": "#795548",
            "Emprendimiento": "#FF9800",
            "Construex University": "#2196F3",
            "Salud": "#4CAF50",
            "Automejora": "#9C27B0"
        };
        
        async function procesar() {
            const url = document.getElementById('urlInput').value;
            if (!url) { alert('Ingresa una URL'); return; }
            
            const resultadoDiv = document.getElementById('resultado');
            resultadoDiv.style.display = 'block';
            resultadoDiv.innerHTML = '<div>⏳ Procesando enlace...</div>';
            
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
                    resultadoDiv.innerHTML = html;
                    
                    // Generar la imagen
                    generarImagen(data);
                } else {
                    resultadoDiv.innerHTML = `<strong>❌ Error:</strong> ${data.error}`;
                }
            } catch(e) {
                resultadoDiv.innerHTML = `<strong>❌ Error:</strong> ${e.message}`;
            }
        }
        
        function generarImagen(data) {
            const canvas = document.getElementById('imageCanvas');
            const ctx = canvas.getContext('2d');
            
            canvas.width = 1080;
            canvas.height = 1080;
            canvas.style.display = 'block';
            
            const color = colores[data.categoria] || "#3498db";
            
            // Fondo con degradado
            const grad = ctx.createLinearGradient(0, 0, 0, canvas.height);
            grad.addColorStop(0, color);
            grad.addColorStop(1, '#2c3e50');
            ctx.fillStyle = grad;
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            // Marco decorativo
            ctx.strokeStyle = 'rgba(255,255,255,0.2)';
            ctx.lineWidth = 5;
            ctx.strokeRect(40, 40, canvas.width - 80, canvas.height - 80);
            
            // Logo texto
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 36px "Segoe UI"';
            ctx.textAlign = 'center';
            ctx.fillText('🏗️ CONSTRUEX ECOSYSTEM', canvas.width/2, 100);
            
            // Categoría
            ctx.font = 'bold 28px "Segoe UI"';
            ctx.fillStyle = '#FFD700';
            ctx.fillText(`📁 ${data.categoria.toUpperCase()}`, canvas.width/2, 170);
            
            // Línea decorativa
            ctx.beginPath();
            ctx.moveTo(canvas.width/3, 200);
            ctx.lineTo(canvas.width*2/3, 200);
            ctx.strokeStyle = 'rgba(255,255,255,0.3)';
            ctx.lineWidth = 2;
            ctx.stroke();
            
            // Título (con wrap)
            ctx.font = 'bold 48px "Segoe UI"';
            ctx.fillStyle = '#ffffff';
            const tituloLines = wrapText(ctx, data.titulo, canvas.width - 120, 48);
            let y = 270;
            for(let line of tituloLines.slice(0, 3)) {
                ctx.fillText(line, canvas.width/2, y);
                y += 65;
            }
            
            // Línea decorativa
            ctx.beginPath();
            ctx.moveTo(canvas.width/3, y + 10);
            ctx.lineTo(canvas.width*2/3, y + 10);
            ctx.stroke();
            y += 40;
            
            // Resumen
            ctx.font = '26px "Segoe UI"';
            ctx.fillStyle = 'rgba(255,255,255,0.9)';
            const resumenLines = wrapText(ctx, data.resumen, canvas.width - 120, 26);
            for(let line of resumenLines.slice(0, 8)) {
                ctx.fillText(line, canvas.width/2, y);
                y += 40;
            }
            
            // Call to Action
            y = canvas.height - 120;
            ctx.font = 'bold 28px "Segoe UI"';
            ctx.fillStyle = '#FFD700';
            ctx.fillText('✨ Aprende más en Construex ✨', canvas.width/2, y);
            
            // Hashtags
            ctx.font = '22px "Segoe UI"';
            ctx.fillStyle = 'rgba(255,255,255,0.6)';
            ctx.fillText(`#${data.categoria.replace(' ', '')} #Construex #Educacion #Aprende`, canvas.width/2, y + 50);
            
            // Mostrar botón de descarga
            const resultadoDiv = document.getElementById('resultado');
            resultadoDiv.innerHTML += `<div style="margin-top:15px; text-align:center;">
                <button onclick="descargarImagen()" class="descargar">📥 Descargar Imagen (PNG)</button>
                <p style="font-size:12px; color:#666; margin-top:10px;">💡 Imagen lista para Instagram (1080x1080)</p>
            </div>`;
        }
        
        function wrapText(ctx, text, maxWidth, fontSize) {
            ctx.font = `${fontSize}px "Segoe UI"`;
            const words = text.split('');
            const lines = [];
            let currentLine = '';
            
            for(let i = 0; i < words.length; i++) {
                const testLine = currentLine + words[i];
                const metrics = ctx.measureText(testLine);
                if(metrics.width > maxWidth && currentLine.length > 0) {
                    lines.push(currentLine);
                    currentLine = words[i];
                } else {
                    currentLine = testLine;
                }
            }
            lines.push(currentLine);
            return lines;
        }
        
        function descargarImagen() {
            const canvas = document.getElementById('imageCanvas');
            const link = document.createElement('a');
            link.download = `construex_${Date.now()}.png`;
            link.href = canvas.toDataURL();
            link.click();
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
        "resumen": contenido['descripcion'][:350]
    })


@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok", "message": "Sistema Construex funcionando"})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Servidor corriendo en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)