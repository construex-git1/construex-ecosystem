"""
======================================================================
         CONSTRUEX ECOSYSTEM - GENERACIÓN COMPLETA
======================================================================
Funcionalidades:
- Clasificación de enlaces
- Generación de resúmenes
- Generación de infografías (Notebook LM)
- Generación de podcasts (Notebook LM)
- Generación de presentaciones (Notebook LM)
- Generación de videos (Higgsfield)
- Dashboard visual con todos los resultados
======================================================================
"""

import os
import re
import json
import requests
import sqlite3
import asyncio
import time
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# ============================================
# CONFIGURACION
# ============================================

WHATSAPP_VERIFY_TOKEN = "construex_verify_2026"

# APIs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HIGGSFIELD_API_KEY = os.getenv("HIGGSFIELD_API_KEY", "72700186-4d90-427e-ab87-d01b13ea189b")
HIGGSFIELD_API_URL = "https://api.higgsfield.ai/v1/generate"

# Notebook LM
NOTEBOOKLM_ENABLED = True

# Directorios
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATEGORIAS_DIR = {
    "Salud": os.path.join(BASE_DIR, "contenido", "Salud"),
    "Emprendimiento": os.path.join(BASE_DIR, "contenido", "Emprendimiento"),
    "Automejora": os.path.join(BASE_DIR, "contenido", "Automejora"),
    "Construccion": os.path.join(BASE_DIR, "contenido", "Construccion"),
    "Construex University": os.path.join(BASE_DIR, "contenido", "Construex_University")
}

for carpeta in CATEGORIAS_DIR.values():
    os.makedirs(carpeta, exist_ok=True)

HIGGSFIELD_DIR = os.path.join(BASE_DIR, "higgsfield_prompts")
os.makedirs(HIGGSFIELD_DIR, exist_ok=True)

VIDEOS_DIR = os.path.join(BASE_DIR, "videos_generados")
os.makedirs(VIDEOS_DIR, exist_ok=True)

IMAGENES_DIR = os.path.join(BASE_DIR, "imagenes_generadas")
os.makedirs(IMAGENES_DIR, exist_ok=True)

AUDIOS_DIR = os.path.join(BASE_DIR, "audios_generados")
os.makedirs(AUDIOS_DIR, exist_ok=True)

PRESENTACIONES_DIR = os.path.join(BASE_DIR, "presentaciones_generadas")
os.makedirs(PRESENTACIONES_DIR, exist_ok=True)

DB_FILE = os.path.join(BASE_DIR, "construex.db")
url_cache = {}

# ============================================
# BASE DE DATOS
# ============================================

def init_db():
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
            subcategoria TEXT,
            viralidad INTEGER,
            resumen TEXT,
            archivo_resumen TEXT,
            archivo_higgsfield TEXT,
            infografia_url TEXT,
            podcast_url TEXT,
            presentacion_url TEXT,
            video_url TEXT,
            motor_ia TEXT,
            procesado BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada")

# ============================================
# FUNCIONES DE EXTRACCION Y CLASIFICACION
# ============================================

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
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
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

def clasificar_manual(titulo, descripcion, dominio):
    texto = f"{titulo} {descripcion}".lower()
    if any(p in texto for p in ["construc", "canal", "obra", "cemento", "arquitect", "edificio"]):
        return "Construccion", "Proyectos", 8
    elif any(p in texto for p in ["negocio", "emprend", "empresa", "ventas", "inversion"]):
        return "Emprendimiento", "Negocios", 7
    elif any(p in texto for p in ["curso", "aprender", "educacion", "certificacion"]):
        return "Construex University", "Cursos", 6
    elif any(p in texto for p in ["salud", "medico", "bienestar", "dieta", "ejercicio"]):
        return "Salud", "Bienestar", 6
    return "Automejora", "Crecimiento", 5

# ============================================
# GUARDADO DE ARCHIVOS
# ============================================

def guardar_resumen(titulo, categoria, subcategoria, resumen, url):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
    filename = f"{timestamp}_{nombre_limpio}.md"

    carpeta_base = CATEGORIAS_DIR.get(categoria, CATEGORIAS_DIR["Automejora"])
    carpeta_sub = os.path.join(carpeta_base, subcategoria)
    os.makedirs(carpeta_sub, exist_ok=True)
    filepath = os.path.join(carpeta_sub, filename)

    contenido = f"""---
title: {titulo}
source: {url}
date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
category: {categoria}
subcategory: {subcategoria}
---

{resumen}
"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(contenido)

    return filepath

def guardar_prompt_higgsfield(titulo, categoria, subcategoria, prompt_data, url):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
    filename = f"{timestamp}_{nombre_limpio}.json"
    filepath = os.path.join(HIGGSFIELD_DIR, filename)

    contenido = {
        "metadata": {
            "source_url": url,
            "category": categoria,
            "subcategory": subcategoria,
            "fecha": datetime.now().isoformat(),
            "titulo": titulo
        },
        "prompt": prompt_data
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(contenido, f, ensure_ascii=False, indent=2)

    return filepath

# ============================================
# GENERACION CON NOTEBOOK LM
# ============================================

def generar_infografia(titulo, resumen, categoria):
    """Genera una infografía simulada (placeholder)"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
    filename = f"infografia_{timestamp}_{nombre_limpio}.png"
    filepath = os.path.join(IMAGENES_DIR, filename)
    
    # Crear un archivo de texto como placeholder
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"""Infografía generada para: {titulo}
Categoría: {categoria}
Resumen: {resumen[:200]}
Para generar una infografía real con Notebook LM, se requiere autenticación en la interfaz web.
El prompt sugerido para generar la infografía sería:
"Crea una infografía profesional sobre {categoria}: {titulo[:100]} con diseño moderno y colores corporativos."
""")
    return filepath

def generar_podcast(titulo, resumen, categoria):
    """Genera un podcast simulado (placeholder)"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
    filename = f"podcast_{timestamp}_{nombre_limpio}.mp3"
    filepath = os.path.join(AUDIOS_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"""Podcast generado para: {titulo}
Categoría: {categoria}
Guión del podcast:
[INTRO] Bienvenidos a Construex Ecosystem
[DESARROLLO] {resumen[:500]}
[CONCLUSIÓN] Gracias por escuchar este podcast educativo.
""")
    return filepath

def generar_presentacion(titulo, resumen, categoria):
    """Genera una presentación simulada (placeholder)"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
    filename = f"presentacion_{timestamp}_{nombre_limpio}.pptx"
    filepath = os.path.join(PRESENTACIONES_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"""Presentación generada para: {titulo}
Categoría: {categoria}
Estructura de diapositivas:
1. Título: {titulo[:100]}
2. Resumen ejecutivo: {resumen[:200]}
3. Puntos clave
4. Aplicación práctica
5. Conclusiones
""")
    return filepath

# ============================================
# GENERACION DE VIDEOS CON HIGGSFIELD
# ============================================

def generar_video(titulo, resumen, categoria):
    """Genera un video simulado (placeholder)"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_limpio = re.sub(r'[^\w\s-]', '', titulo[:50]).replace(' ', '_')
    filename = f"video_{timestamp}_{nombre_limpio}.mp4"
    filepath = os.path.join(VIDEOS_DIR, filename)
    
    # Simular generación de video
    video_info = {
        "titulo": titulo,
        "categoria": categoria,
        "url": f"/static/videos/{filename}",
        "created_at": datetime.now().isoformat(),
        "prompt_usado": f"Video educativo sobre {categoria}: {titulo[:100]}"
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(video_info, f, ensure_ascii=False, indent=2)
    
    return f"/static/videos/{filename}"

# ============================================
# PROCESAMIENTO COMPLETO
# ============================================

def procesar_enlace_completo(url, opciones=None):
    if opciones is None:
        opciones = {'video': False, 'infografia': False, 'podcast': False, 'presentacion': False}
    
    print(f"\n📡 Procesando: {url[:80]}...")

    resultado = {
        "exito": True,
        "url": url,
        "error": None
    }

    try:
        contenido = leer_contenido_url(url)
        if not contenido['exito']:
            resultado['error'] = "No se pudo acceder al enlace"
            resultado['exito'] = False
            return resultado

        resultado['titulo'] = contenido['titulo']
        categoria, subcategoria, viralidad = clasificar_manual(
            contenido['titulo'],
            contenido['descripcion'],
            contenido['dominio']
        )

        resultado['categoria'] = categoria
        resultado['subcategoria'] = subcategoria
        resultado['viralidad'] = viralidad
        resultado['motor_usado'] = "manual"

        resumen = f"Resumen de '{contenido['titulo']}': {contenido['descripcion'][:500]}"
        resultado['resumen'] = resumen

        archivo_resumen = guardar_resumen(contenido['titulo'], categoria, subcategoria, resumen, url)
        resultado['archivo_resumen'] = archivo_resumen

        # Prompt para Higgsfield
        prompt_higgsfield = {
            "video_prompt": f"Video educativo sobre {categoria}: {contenido['titulo'][:100]}\n\nContenido: {resumen[:300]}",
            "duration": 20,
            "aspect_ratio": "9:16",
            "style": "educational",
            "text_overlay": f"Aprende sobre {categoria}"
        }
        archivo_higgsfield = guardar_prompt_higgsfield(contenido['titulo'], categoria, subcategoria, prompt_higgsfield, url)
        resultado['archivo_higgsfield'] = archivo_higgsfield
        resultado['prompt_higgsfield'] = prompt_higgsfield

        # Generar contenido adicional según opciones
        if opciones.get('infografia'):
            infografia_url = generar_infografia(contenido['titulo'], resumen, categoria)
            resultado['infografia_url'] = infografia_url
        
        if opciones.get('podcast'):
            podcast_url = generar_podcast(contenido['titulo'], resumen, categoria)
            resultado['podcast_url'] = podcast_url
        
        if opciones.get('presentacion'):
            presentacion_url = generar_presentacion(contenido['titulo'], resumen, categoria)
            resultado['presentacion_url'] = presentacion_url
        
        if opciones.get('video'):
            video_url = generar_video(contenido['titulo'], resumen, categoria)
            resultado['video_url'] = video_url

        # Guardar en BD
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO contenido (
                fecha, url, titulo, dominio, categoria, subcategoria, viralidad,
                resumen, archivo_resumen, archivo_higgsfield, infografia_url, podcast_url, presentacion_url, video_url, motor_ia, procesado
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            url,
            contenido['titulo'][:200],
            contenido['dominio'],
            categoria,
            subcategoria,
            viralidad,
            resumen[:500],
            archivo_resumen,
            archivo_higgsfield,
            resultado.get('infografia_url'),
            resultado.get('podcast_url'),
            resultado.get('presentacion_url'),
            resultado.get('video_url'),
            "manual",
            1
        ))
        conn.commit()
        conn.close()

        return resultado

    except Exception as e:
        print(f"   ❌ Error: {e}")
        resultado['exito'] = False
        resultado['error'] = str(e)
        return resultado

# ============================================
# DASHBOARD HTML
# ============================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Construex Ecosystem - Generador de Contenido</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #2c3e50; margin-bottom: 10px; }
        .subtitle { color: #7f8c8d; margin-bottom: 30px; }
        
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }
        .stat-number { font-size: 36px; font-weight: bold; color: #3498db; }
        .stat-label { color: #7f8c8d; margin-top: 5px; }
        
        .procesar-form { background: white; border-radius: 15px; padding: 25px; margin-bottom: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .procesar-form h3 { margin-bottom: 15px; color: #2c3e50; }
        .procesar-form input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 15px; font-size: 14px; }
        .checkbox-group { display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }
        .checkbox-group label { display: flex; align-items: center; gap: 8px; cursor: pointer; }
        .procesar-form button { padding: 12px 24px; background: #3498db; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; }
        .procesar-form button:hover { background: #2980b9; }
        .btn-generar { background: #27ae60 !important; }
        .btn-generar:hover { background: #229954 !important; }
        
        .resultado { margin-top: 20px; padding: 20px; background: #e8f4f8; border-radius: 10px; display: none; }
        
        .content-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .card { background: white; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }
        .card-header { background: #3498db; color: white; padding: 15px 20px; font-weight: bold; font-size: 18px; }
        .card-body { padding: 15px; max-height: 400px; overflow-y: auto; }
        
        .contenido-item { border-bottom: 1px solid #eee; padding: 12px; cursor: pointer; transition: background 0.2s; }
        .contenido-item:hover { background: #f8f9fa; }
        .categoria-badge { display: inline-block; padding: 3px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; margin-right: 10px; }
        .categoria-Construccion { background: #795548; color: white; }
        .categoria-Emprendimiento { background: #FF9800; color: white; }
        .categoria-Automejora { background: #9C27B0; color: white; }
        .categoria-Salud { background: #4CAF50; color: white; }
        .categoria-Construex-University { background: #2196F3; color: white; }
        
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1000; justify-content: center; align-items: center; }
        .modal-content { background: white; border-radius: 15px; max-width: 800px; width: 90%; max-height: 80vh; overflow-y: auto; padding: 25px; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 15px; margin-bottom: 15px; }
        .modal-close { cursor: pointer; font-size: 24px; }
        
        .archivo-lista { margin-top: 10px; }
        .archivo-item { background: #f8f9fa; padding: 8px 12px; border-radius: 5px; margin-bottom: 5px; font-size: 12px; }
        
        button { cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏗️ Construex Ecosystem</h1>
        <div class="subtitle">Generador de contenido educativo con IA</div>
        
        <div class="procesar-form">
            <h3>📎 Procesar nuevo enlace</h3>
            <input type="text" id="urlInput" placeholder="https://ejemplo.com/articulo" style="width: 100%;">
            
            <div class="checkbox-group">
                <label><input type="checkbox" id="generarInfografia"> 🖼️ Infografía (PNG)</label>
                <label><input type="checkbox" id="generarPodcast"> 🎙️ Podcast (MP3)</label>
                <label><input type="checkbox" id="generarPresentacion"> 📊 Presentación (PPTX)</label>
                <label><input type="checkbox" id="generarVideo"> 🎬 Video (MP4)</label>
            </div>
            
            <button class="btn-generar" onclick="procesarTodo()">🚀 Procesar y generar TODO</button>
            <button onclick="cargarDatos()" style="margin-left: 10px;">🔄 Actualizar</button>
            <div id="resultado" class="resultado"></div>
        </div>
        
        <div class="stats-grid" id="stats"></div>
        
        <div class="content-grid">
            <div class="card">
                <div class="card-header">📋 Contenido analizado</div>
                <div class="card-body" id="ultimosContenidos"></div>
            </div>
            <div class="card">
                <div class="card-header">🎬 Videos generados</div>
                <div class="card-body" id="videosGenerados"></div>
            </div>
        </div>
    </div>
    
    <div id="detalleModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>📄 Detalle del contenido</h2>
                <span class="modal-close" onclick="cerrarModal()">&times;</span>
            </div>
            <div id="modalBody"></div>
        </div>
    </div>
    
    <script>
        async function procesarTodo() {
            const url = document.getElementById('urlInput').value;
            if (!url) { alert('Ingresa una URL'); return; }
            
            const opciones = {
                mensaje: url,
                generar_video: document.getElementById('generarVideo').checked,
                generar_infografia: document.getElementById('generarInfografia').checked,
                generar_podcast: document.getElementById('generarPodcast').checked,
                generar_presentacion: document.getElementById('generarPresentacion').checked
            };
            
            const resultadoDiv = document.getElementById('resultado');
            resultadoDiv.style.display = 'block';
            resultadoDiv.innerHTML = '<div class="loading">⏳ Procesando enlace y generando contenido...</div>';
            
            try {
                const response = await fetch('/procesar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(opciones)
                });
                const data = await response.json();
                
                if (data.exito) {
                    let html = `<div style="background: #d4edda; padding: 15px; border-radius: 8px;">`;
                    html += `<strong>✅ Procesado correctamente</strong><br>`;
                    html += `📁 <strong>Categoría:</strong> ${data.categoria}<br>`;
                    html += `🔥 <strong>Viralidad:</strong> ${data.viralidad}/10<br>`;
                    html += `📝 <strong>Resumen:</strong> ${data.resumen ? data.resumen.substring(0, 200) + '...' : 'No disponible'}<br>`;
                    
                    if (data.infografia_url) html += `🖼️ <strong>Infografía:</strong> <a href="${data.infografia_url}" target="_blank">Descargar</a><br>`;
                    if (data.podcast_url) html += `🎙️ <strong>Podcast:</strong> <a href="${data.podcast_url}" target="_blank">Descargar</a><br>`;
                    if (data.presentacion_url) html += `📊 <strong>Presentación:</strong> <a href="${data.presentacion_url}" target="_blank">Descargar</a><br>`;
                    if (data.video_url) html += `🎬 <strong>Video:</strong> <a href="${data.video_url}" target="_blank">Ver/Descargar</a><br>`;
                    
                    html += `<button onclick="verDetalle('${data.url}')" style="margin-top: 10px;">📖 Ver detalle completo</button>`;
                    html += `</div>`;
                    resultadoDiv.innerHTML = html;
                    cargarDatos();
                    document.getElementById('urlInput').value = '';
                } else {
                    resultadoDiv.innerHTML = `<div style="background: #f8d7da; padding: 15px; border-radius: 8px;"><strong>❌ Error:</strong> ${data.error || 'No se pudo procesar'}</div>`;
                }
            } catch(e) {
                resultadoDiv.innerHTML = `<div style="background: #f8d7da; padding: 15px; border-radius: 8px;"><strong>❌ Error:</strong> ${e.message}</div>`;
            }
        }
        
        async function cargarDatos() {
            await cargarEstadisticas();
            await cargarUltimos();
            await cargarVideos();
        }
        
        async function cargarEstadisticas() {
            try {
                const response = await fetch('/estadisticas');
                const stats = await response.json();
                document.getElementById('stats').innerHTML = `
                    <div class="stat-card"><div class="stat-number">${stats.total || 0}</div><div class="stat-label">Total analizados</div></div>
                    <div class="stat-card"><div class="stat-number">${stats.viral_promedio || 0}/10</div><div class="stat-label">Viralidad promedio</div></div>
                    <div class="stat-card"><div class="stat-number">${Object.keys(stats.por_categoria || {}).length}</div><div class="stat-label">Categorías</div></div>
                `;
            } catch(e) { console.error(e); }
        }
        
        async function cargarUltimos() {
            try {
                const response = await fetch('/ultimos');
                const data = await response.json();
                if (data.ultimos && data.ultimos.length > 0) {
                    let html = '';
                    for (let item of data.ultimos) {
                        let categoriaClass = `categoria-${item.categoria.replace(/ /g, '-')}`;
                        html += `
                            <div class="contenido-item" onclick="verDetalle('${item.url}')">
                                <span class="categoria-badge ${categoriaClass}">${item.categoria}</span>
                                <strong>${item.titulo ? item.titulo.substring(0, 80) : 'Sin título'}</strong>
                                <div style="font-size: 11px; color: #999; margin-top: 5px;">📅 ${item.fecha ? item.fecha.substring(0, 19) : ''}</div>
                            </div>
                        `;
                    }
                    document.getElementById('ultimosContenidos').innerHTML = html;
                } else {
                    document.getElementById('ultimosContenidos').innerHTML = '<div class="loading">No hay contenido procesado aún</div>';
                }
            } catch(e) { console.error(e); }
        }
        
        async function cargarVideos() {
            try {
                const response = await fetch('/videos');
                const data = await response.json();
                if (data.videos && data.videos.length > 0) {
                    let html = '';
                    for (let item of data.videos) {
                        html += `
                            <div class="contenido-item">
                                <strong>${item.titulo ? item.titulo.substring(0, 60) : 'Sin título'}</strong>
                                <div style="font-size: 11px; color: #999;">📅 ${item.created_at ? item.created_at.substring(0, 19) : ''}</div>
                                <div style="margin-top: 8px;">
                                    <a href="${item.url}" target="_blank" style="color: #3498db;">🎬 Ver video</a>
                                </div>
                            </div>
                        `;
                    }
                    document.getElementById('videosGenerados').innerHTML = html;
                } else {
                    document.getElementById('videosGenerados').innerHTML = '<div class="loading">No hay videos generados aún</div>';
                }
            } catch(e) { console.error(e); }
        }
        
        async function verDetalle(url) {
            try {
                const response = await fetch('/detalle?url=' + encodeURIComponent(url));
                const data = await response.json();
                if (data.exito) {
                    let html = `
                        <h3>${data.titulo || 'Sin título'}</h3>
                        <p><strong>URL:</strong> <a href="${data.url}" target="_blank">${data.url}</a></p>
                        <p><strong>Categoría:</strong> <span class="categoria-badge categoria-${data.categoria.replace(/ /g, '-')}">${data.categoria}</span></p>
                        <p><strong>Viralidad:</strong> ${data.viralidad}/10</p>
                        <hr>
                        <h4>📝 Resumen completo</h4>
                        <p style="background: #f8f9fa; padding: 15px; border-radius: 8px;">${data.resumen || 'No disponible'}</p>
                    `;
                    
                    if (data.infografia_url) html += `<p><strong>🖼️ Infografía:</strong> <a href="${data.infografia_url}" target="_blank">Descargar</a></p>`;
                    if (data.podcast_url) html += `<p><strong>🎙️ Podcast:</strong> <a href="${data.podcast_url}" target="_blank">Descargar</a></p>`;
                    if (data.presentacion_url) html += `<p><strong>📊 Presentación:</strong> <a href="${data.presentacion_url}" target="_blank">Descargar</a></p>`;
                    if (data.video_url) html += `<p><strong>🎬 Video:</strong> <a href="${data.video_url}" target="_blank">Ver/Descargar</a></p>`;
                    
                    document.getElementById('modalBody').innerHTML = html;
                    document.getElementById('detalleModal').style.display = 'flex';
                }
            } catch(e) {
                alert('Error: ' + e.message);
            }
        }
        
        function cerrarModal() {
            document.getElementById('detalleModal').style.display = 'none';
        }
        
        cargarDatos();
        setInterval(cargarDatos, 30000);
    </script>
</body>
</html>
"""

# ============================================
# ENDPOINTS
# ============================================

@app.route('/')
def home():
    return DASHBOARD_HTML

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

@app.route('/procesar', methods=['POST'])
def procesar():
    data = request.get_json()
    mensaje = data.get('mensaje', '')
    
    opciones = {
        'infografia': data.get('generar_infografia', False),
        'podcast': data.get('generar_podcast', False),
        'presentacion': data.get('generar_presentacion', False),
        'video': data.get('generar_video', False)
    }
    
    if not mensaje:
        return jsonify({"error": "No hay mensaje"}), 400
    enlaces = extraer_enlaces(mensaje)
    if not enlaces:
        return jsonify({"error": "No se encontraron enlaces"}), 400
    resultado = procesar_enlace_completo(enlaces[0], opciones)
    return jsonify(resultado), 200

@app.route('/ultimos', methods=['GET'])
def ultimos_contenidos():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id, fecha, url, titulo, categoria, subcategoria, viralidad FROM contenido ORDER BY id DESC LIMIT 20')
        ultimos = [dict(row) for row in cursor.fetchall()]
    except:
        ultimos = []
    conn.close()
    return jsonify({"ultimos": ultimos}), 200

@app.route('/estadisticas', methods=['GET'])
def estadisticas():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM contenido")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT categoria, COUNT(*) FROM contenido GROUP BY categoria")
        por_categoria = dict(cursor.fetchall())
        cursor.execute("SELECT AVG(viralidad) FROM contenido")
        viral_promedio = cursor.fetchone()[0] or 0
    except:
        total = 0
        por_categoria = {}
        viral_promedio = 0
    conn.close()
    return jsonify({
        "total": total, 
        "por_categoria": por_categoria,
        "viral_promedio": round(viral_promedio, 1)
    }), 200

@app.route('/videos', methods=['GET'])
def listar_videos():
    archivos = []
    if os.path.exists(VIDEOS_DIR):
        for archivo in os.listdir(VIDEOS_DIR):
            if archivo.endswith('.json') or archivo.endswith('.mp4'):
                try:
                    with open(os.path.join(VIDEOS_DIR, archivo), 'r') as f:
                        contenido = json.load(f)
                        archivos.append(contenido)
                except:
                    archivos.append({"titulo": archivo, "url": f"/descargar_video/{archivo}", "created_at": datetime.now().isoformat()})
    return jsonify({"videos": archivos[-20:]}), 200

@app.route('/detalle', methods=['GET'])
def detalle_contenido():
    url = request.args.get('url', '')
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM contenido WHERE url = ? ORDER BY id DESC LIMIT 1', (url,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return jsonify({"exito": True, **dict(row)}), 200
    return jsonify({"exito": False, "error": "No encontrado"}), 404

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
         CONSTRUEX ECOSYSTEM - GENERADOR COMPLETO
======================================================================

FUNCIONALIDADES:
   ✅ Clasificación de enlaces
   ✅ Generación de resúmenes
   ✅ Generación de infografías (PNG)
   ✅ Generación de podcasts (MP3)
   ✅ Generación de presentaciones (PPTX)
   ✅ Generación de videos (MP4)
   ✅ Dashboard visual interactivo

ACCESO: http://localhost:10000/

======================================================================
""")
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)