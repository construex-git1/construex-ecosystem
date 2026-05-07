"""
======================================================================
         CONSTRUEX ECOSYSTEM - VERSIÓN VIRAL
======================================================================
"""

import os
import re
import requests
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
app = Flask(__name__)

# Configurar Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')


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


def generar_contenido_viral_con_gemini(titulo, descripcion, categoria):
    """Genera contenido viral usando Gemini"""
    
    prompt = f"""
    Eres un experto en marketing viral. Crea contenido para Instagram basado en este artículo:
    
    TÍTULO: {titulo}
    CATEGORÍA: {categoria}
    CONTENIDO: {descripcion[:800]}
    
    Genera un formato viral que incluya:
    
    1. UN TÍTULO CLICKBAIT (máx 60 caracteres) que haga que la gente quiera leer
    2. UN DATO SORPRENDENTE (el "hook" que hace que la gente comente)
    3. 4 PUNTOS CLAVE con emojis (cada punto debe ser valioso y compartible)
    4. UN CALL TO ACTION VIRAL (frase que invite a guardar/compartir)
    5. 5 HASHTAGS TENDENCIA relacionados
    
    Responde SOLO con JSON en este formato:
    {{
        "titulo_viral": "...",
        "dato_sorprendente": "...",
        "puntos_clave": ["punto1", "punto2", "punto3", "punto4"],
        "call_to_action": "...",
        "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]
    }}
    """
    
    try:
        respuesta = gemini_model.generate_content(prompt)
        texto = respuesta.text
        if "```json" in texto:
            texto = texto.split("```json")[1].split("```")[0]
        import json
        return json.loads(texto.strip())
    except Exception as e:
        print(f"Error Gemini: {e}")
        return {
            "titulo_viral": f"🔥 {titulo[:55]} 🔥",
            "dato_sorprendente": descripcion[:150],
            "puntos_clave": [descripcion[i:i+80] for i in range(0, 320, 80)][:4],
            "call_to_action": "✨ Guarda este post para después y compártelo con alguien que debería saber esto ✨",
            "hashtags": [f"#{categoria}", "#Construex", "#Educacion", "#Aprende", "#Viral"]
        }


def clasificar_manual(titulo, descripcion, dominio):
    texto = f"{titulo} {descripcion}".lower()
    if any(p in texto for p in ["construc", "centro comercial", "mall", "obra", "empleo", "edificio"]):
        return "Construccion"
    elif any(p in texto for p in ["negocio", "emprend", "empresa", "ventas"]):
        return "Emprendimiento"
    elif any(p in texto for p in ["curso", "aprender", "educacion"]):
        return "Construex University"
    elif any(p in texto for p in ["salud", "medico", "bienestar"]):
        return "Salud"
    return "Automejora"


@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Construex - Contenido Viral</title>
        <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f0f0f; min-height: 100vh; display: flex; justify-content: center; align-items: center; padding: 20px; }
            .container { max-width: 600px; width: 100%; }
            .card { background: #1a1a2e; border-radius: 24px; padding: 25px; margin-bottom: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.4); }
            h1 { color: white; font-size: 28px; margin-bottom: 5px; }
            .sub { color: #aaa; font-size: 14px; margin-bottom: 20px; }
            input { width: 100%; padding: 14px; background: #2a2a3e; border: 1px solid #3a3a4e; border-radius: 12px; color: white; font-size: 14px; margin-bottom: 15px; }
            button { width: 100%; background: linear-gradient(135deg, #FF6B6B, #FF8E53); color: white; padding: 14px; border: none; border-radius: 12px; font-size: 16px; font-weight: bold; cursor: pointer; transition: transform 0.2s; }
            button:hover { transform: scale(1.02); }
            .loading { text-align: center; padding: 30px; color: #aaa; display: none; }
            .preview { margin-top: 20px; display: none; }
            .carousel { display: flex; overflow-x: auto; gap: 20px; padding: 10px 0; scroll-snap-type: x mandatory; }
            .slide { scroll-snap-align: start; min-width: 100%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 24px; overflow: hidden; box-shadow: 0 15px 35px rgba(0,0,0,0.3); }
            .slide-content { padding: 40px; color: white; }
            .slide-number { position: absolute; bottom: 20px; right: 25px; background: rgba(0,0,0,0.5); padding: 5px 12px; border-radius: 20px; font-size: 12px; }
            .titulo-viral { font-size: 32px; font-weight: bold; margin-bottom: 20px; line-height: 1.3; }
            .dato { background: rgba(0,0,0,0.3); border-radius: 16px; padding: 20px; margin: 20px 0; border-left: 4px solid #FFD700; }
            .punto { display: flex; align-items: flex-start; gap: 15px; margin-bottom: 20px; }
            .punto-emoji { font-size: 28px; min-width: 50px; }
            .punto-texto { font-size: 16px; line-height: 1.4; }
            .cta { background: #FFD700; color: #1a1a2e; padding: 15px; border-radius: 16px; text-align: center; font-weight: bold; margin: 20px 0; }
            .hashtags { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 20px; }
            .hashtag { background: rgba(255,255,255,0.2); padding: 6px 14px; border-radius: 20px; font-size: 12px; }
            .controls { display: flex; justify-content: space-between; margin-top: 15px; gap: 10px; }
            .nav-btn { background: #333; padding: 10px; width: auto; font-size: 14px; margin: 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <h1>🔥 Construex Viral</h1>
                <div class="sub">Genera contenido viral para Instagram</div>
                
                <input type="text" id="urlInput" placeholder="https://ejemplo.com/articulo">
                <button id="generateBtn">🚀 Generar Contenido Viral</button>
                
                <div class="loading" id="loading">⏳ Analizando y generando contenido viral...</div>
            </div>
            
            <div class="preview" id="preview">
                <div id="carousel" class="carousel"></div>
                <div class="controls">
                    <button class="nav-btn" id="prevBtn">◀ Anterior</button>
                    <button class="nav-btn" id="nextBtn">Siguiente ▶</button>
                    <button class="nav-btn" id="downloadBtn">📥 Descargar Todo</button>
                </div>
                <div class="info-box" style="background: #2a2a3e; padding: 12px; border-radius: 12px; margin-top: 15px; color: #aaa; font-size: 12px; text-align: center;">
                    💡 Múltiples diapositivas para carrusel de Instagram. Descarga cada una como PNG.
                </div>
            </div>
        </div>

        <script>
        let currentSlide = 0;
        let slides = [];
        
        document.getElementById('generateBtn').addEventListener('click', procesar);
        document.getElementById('prevBtn').addEventListener('click', () => cambiarSlide(-1));
        document.getElementById('nextBtn').addEventListener('click', () => cambiarSlide(1));
        document.getElementById('downloadBtn').addEventListener('click', descargarTodo);
        
        async function procesar() {
            const url = document.getElementById('urlInput').value;
            if (!url) { alert('Ingresa una URL'); return; }
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('preview').style.display = 'none';
            
            try {
                const response = await fetch('/procesar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mensaje: url })
                });
                const data = await response.json();
                
                if (data.exito) {
                    generarCarousel(data);
                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('preview').style.display = 'block';
                } else {
                    mostrarError(data.error);
                }
            } catch(e) {
                mostrarError('Error de conexión: ' + e.message);
            }
        }
        
        function generarCarousel(data) {
            const colores = {
                "Construccion": "linear-gradient(135deg, #795548 0%, #3e2723 100%)",
                "Emprendimiento": "linear-gradient(135deg, #FF9800 0%, #e65100 100%)",
                "Construex University": "linear-gradient(135deg, #2196F3 0%, #0d47a1 100%)",
                "Salud": "linear-gradient(135deg, #4CAF50 0%, #1b5e20 100%)",
                "Automejora": "linear-gradient(135deg, #9C27B0 0%, #4a148c 100%)"
            };
            const gradient = colores[data.categoria] || "linear-gradient(135deg, #667eea 0%, #764ba2 100%)";
            
            slides = [
                // Slide 1 - Portada viral
                `<div class="slide" style="background: ${gradient}; position: relative;">
                    <div class="slide-content" style="text-align: center;">
                        <div style="font-size: 80px; margin-bottom: 30px;">🔥</div>
                        <div class="titulo-viral">${data.titulo_viral || data.titulo}</div>
                        <div style="font-size: 18px; opacity: 0.9; margin-top: 30px;">👇 Desliza para descubrir 👇</div>
                    </div>
                    <div class="slide-number">1/5</div>
                </div>`,
                
                // Slide 2 - Dato sorprendente
                `<div class="slide" style="background: ${gradient}; position: relative;">
                    <div class="slide-content">
                        <div style="font-size: 24px; margin-bottom: 20px;">💥 DATO IMPACTANTE</div>
                        <div class="dato" style="background: rgba(0,0,0,0.3);">
                            <div style="font-size: 20px; font-weight: bold;">"${data.dato_sorprendente}"</div>
                        </div>
                        <div style="margin-top: 30px; text-align: center;">🤯 ¿Lo sabías?</div>
                    </div>
                    <div class="slide-number">2/5</div>
                </div>`,
                
                // Slide 3 - Puntos clave
                `<div class="slide" style="background: ${gradient}; position: relative;">
                    <div class="slide-content">
                        <div style="font-size: 24px; margin-bottom: 20px;">📌 PUNTOS CLAVE</div>
                        ${data.puntos_clave.map((p, i) => `
                            <div class="punto">
                                <div class="punto-emoji">${["1️⃣","2️⃣","3️⃣","4️⃣"][i] || "📌"}</div>
                                <div class="punto-texto">${p}</div>
                            </div>
                        `).join('')}
                    </div>
                    <div class="slide-number">3/5</div>
                </div>`,
                
                // Slide 4 - Call to action
                `<div class="slide" style="background: ${gradient}; position: relative;">
                    <div class="slide-content" style="text-align: center;">
                        <div style="font-size: 60px; margin-bottom: 20px;">✨</div>
                        <div class="cta" style="background: #FFD700; color: #1a1a2e;">
                            ${data.call_to_action}
                        </div>
                        <div style="margin-top: 30px;">💾 <strong>GUARDA ESTE POST</strong> 💾</div>
                        <div>👥 <strong>COMPARTE CON ALGUIEN</strong> 👥</div>
                    </div>
                    <div class="slide-number">4/5</div>
                </div>`,
                
                // Slide 5 - Hashtags
                `<div class="slide" style="background: ${gradient}; position: relative;">
                    <div class="slide-content" style="text-align: center;">
                        <div style="font-size: 24px; margin-bottom: 30px;">🏷️ SIGUE APRENDIENDO</div>
                        <div class="hashtags" style="justify-content: center;">
                            ${data.hashtags.map(h => `<span class="hashtag">${h}</span>`).join('')}
                        </div>
                        <div style="margin-top: 40px;">
                            <div style="font-size: 20px;">🏗️ <strong>Construex</strong></div>
                            <div style="font-size: 14px; opacity: 0.7;">La mejor educación para profesionales</div>
                        </div>
                    </div>
                    <div class="slide-number">5/5</div>
                </div>`
            ];
            
            const carousel = document.getElementById('carousel');
            carousel.innerHTML = slides.join('');
            currentSlide = 0;
            actualizarVisibilidad();
        }
        
        function cambiarSlide(direccion) {
            currentSlide += direccion;
            if (currentSlide < 0) currentSlide = slides.length - 1;
            if (currentSlide >= slides.length) currentSlide = 0;
            actualizarVisibilidad();
        }
        
        function actualizarVisibilidad() {
            const carousel = document.getElementById('carousel');
            const slideWidth = carousel.querySelector('.slide')?.offsetWidth || 550;
            carousel.scrollTo({ left: currentSlide * slideWidth, behavior: 'smooth' });
        }
        
        async function descargarTodo() {
            const carousel = document.getElementById('carousel');
            const slidesElements = carousel.querySelectorAll('.slide');
            
            for (let i = 0; i < slidesElements.length; i++) {
                const canvas = await html2canvas(slidesElements[i], { scale: 2 });
                const link = document.createElement('a');
                link.download = `construex_slide_${i+1}_${Date.now()}.png`;
                link.href = canvas.toDataURL();
                link.click();
                await new Promise(r => setTimeout(r, 500));
            }
            alert(`✅ ${slidesElements.length} imágenes descargadas!`);
        }
        
        function mostrarError(msg) {
            document.getElementById('loading').style.display = 'none';
            alert('❌ ' + msg);
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
    
    categoria = clasificar_manual(contenido['titulo'], contenido['descripcion'], contenido['dominio'])
    
    if GEMINI_API_KEY:
        contenido_viral = generar_contenido_viral_con_gemini(contenido['titulo'], contenido['descripcion'], categoria)
    else:
        contenido_viral = {
            "titulo_viral": f"🔥 {contenido['titulo'][:55]} 🔥",
            "dato_sorprendente": contenido['descripcion'][:150],
            "puntos_clave": [contenido['descripcion'][i:i+80] for i in range(0, 320, 80)][:4],
            "call_to_action": "✨ Guarda este post y compártelo ✨",
            "hashtags": [f"#{categoria}", "#Construex", "#Educacion", "#Viral", "#Aprende"]
        }
    
    return jsonify({
        "exito": True,
        "categoria": categoria,
        "titulo": contenido['titulo'],
        "contenido_viral": contenido_viral
    })


@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok", "message": "Sistema Construex funcionando"})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Servidor corriendo en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)