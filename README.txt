======================================================================
          CONSTRUEX ECOSYSTEM - DOCUMENTACIÓN COMPLETA DEL PROYECTO
======================================================================
Versión: 6.0 
Fecha: 13 de Mayo de 2026
Autor: Equipo de Desarrollo de Construex
Estado del Proyecto: Funcional (Webhook pendiente de publicación en Meta)
======================================================================

ÍNDICE
-------
1.  VISIÓN GENERAL DEL PROYECTO
2.  ARQUITECTURA DEL SISTEMA (EL "FLUJO")
3.  COMPONENTES TÉCNICOS DETALLADOS
    a.  Servidor (Render)
    b.  Base de Código (GitHub)
    c.  Entorno de Ejecución (Python)
    d.  Dependencias (`requirements.txt`)
    e.  Configuración Secreta (`.env`)
4.  INTEGRACIONES Y APIs
    a.  WhatsApp Business (Meta Cloud API)
    b.  Gemini AI (Google)
    c.  Nano Banana Pro (Generación de Imágenes)
    d.  Notion (Base de Datos/Documentación)
    e.  Pollinations.ai (Respaldo para Imágenes)
5.  ESTRUCTURA DE ARCHIVOS DEL PROYECTO (`app.py`)
6.  GUÍA DE IMPLEMENTACIÓN PARA WHATSAPP (PENDIENTE)
    a.  Creación de la App en Meta for Developers
    b.  Configuración del Webhook (Callback URL y Verify Token)
    c.  Publicación de la Aplicación y Modo "Live"
7.  FUNCIONALIDADES IMPLEMENTADAS
8.  CHECKLIST FINAL PARA DEJAR EL SISTEMA 100% OPERATIVO
9.  SOLUCIÓN DE PROBLEMAS COMUNES (TROUBLESHOOTING)

======================================================================
1. VISIÓN GENERAL DEL PROYECTO
======================================================================

El ecosistema Construex es un sistema automatizado de gestión de contenido
educativo. Su función principal es recibir un enlace (noticia, artículo,
blog) a través de un chat de WhatsApp, procesarlo con Inteligencia
Artificial y generar automáticamente múltiples piezas de contenido listas
para publicarse en redes sociales.

**El flujo de alto nivel es:**

Un usuario envía URL → WhatsApp Business API → Webhook en Render →
Extracción del texto (newspaper3k) → Análisis y clasificación (Gemini) →
Generación de imagen (Nano Banana → Pollinations) → Creación de textos
para Instagram/LinkedIn/Twitter → Almacenamiento en Notion → Respuesta
automática al usuario por WhatsApp.

**El "entregable" final de cada URL procesada es:**
- Un hilo para Twitter 
- Un texto para Instagram 
- Un artículo para LinkedIn
- Una imagen profesional generada por IA 
- Un resumen ejecutivo y clasificación del tema
- Trazabilidad de "leads" (potenciales clientes)

======================================================================
2. ARQUITECTURA DEL SISTEMA (EL "FLUJO")
======================================================================

Este es el recorrido completo de un mensaje de WhatsApp a través del sistema:

[ENTRADA] → [PROCESAMIENTO] → [SALIDA]

1.  **ENTRADA (WhatsApp Business API)**
    *   Un usuario envía un mensaje que contiene una URL al número de
        WhatsApp Business `+593 98 393 8439`. (o cualquier número que este verficado por Meta)
    *   Meta (Facebook) reenvía este evento como una solicitud POST a una
        "Callback URL" (nuestro servidor).

2.  **PROCESAMIENTO (Servidor en Render - `app.py`)**
    *   **Webhook Receptor (`/webhook`)**:
        *   Escucha las solicitudes de Meta.
        *   Extrae el número de teléfono del remitente y el texto del mensaje.
        *   Si el mensaje contiene una URL, se inicia un hilo de
            procesamiento en segundo plano.
    *   **Extractor de Contenido (`extraer_noticia()`)**:
        *   Usa la librería `newspaper3k` para descargar y parsear la URL,
        *   obteniendo el título y el texto completo del artículo.
    *   **Analizador IA (`analizar_contenido()`)**:
        *   Envía el título y el texto a la API de **Google Gemini**.
        *   Gemini devuelve un JSON con la categoría principal (Construcción,
            Emprendimiento, Salud, etc.), un resumen ejecutivo, un dato
            impactante, un nivel de confianza y una puntuación de viralidad.
    *   **Generador de Contenido (`generar_texto_redes()`)**:
        *   Toma el análisis de Gemini y genera textos optimizados para
            Instagram, Twitter, LinkedIn y WhatsApp.
    *   **Generador de Imagen (`generar_imagen()`)**:
        *   Intenta generar primero una imagen de alta calidad usando la API
            de Nano Banana Pro.
        *   Si Nano Banana falla (por límite de créditos o error), usa la API
            gratuita de Pollinations.ai como respaldo.
    *   **Detector de Oportunidades (`detectar_oportunidad_lead()`)**:
        *   Analiza el resumen y la categoría.
        *   Si el contenido sugiere una necesidad de compra (ej. "necesito
            presupuesto", "quiero aprender"), se genera un registro de "lead"
            y se guarda en la base de datos local.
    *   **Almacenamiento (`guardar_en_notion()`)**:
        *   Envía el título, URL, categoría, nivel de confianza, viralidad,
            resumen y la URL de la imagen generada a una base de datos de
            **Notion** para su posterior consulta y análisis.
    *   **Respuesta (`enviar_whatsapp()`)**:
        *   Una vez que todo el proceso está completo, envía un mensaje de
            texto de vuelta al usuario original por WhatsApp, notificándole que
            el contenido ha sido procesado y almacenado.

3.  **SALIDA (Destinos finales)**
    *   **Respuesta en el chat de WhatsApp**: Confirmación al usuario.
    *   **Notion**: El contenido procesado queda organizado y listo para que el
        equipo de Construex lo revise y lo publique manualmente, o para que
        otros sistemas lo tomen.
    *   **Archivos locales en Render**: La imagen generada se guarda en el
        servidor. A futuro, podría subirse automáticamente a redes sociales.

======================================================================
3. COMPONENTES TÉCNICOS DETALLADOS
======================================================================

a. Servidor (Infraestructura)
   - **Plataforma**: Render.com (Plan gratuito)
   - **Estado**: Activo y en línea (`https://construex-ecosystem.onrender.com`)
   - **Función**: Aloja la aplicación Python, ejecuta el webhook y procesa los
     mensajes. También almacena las imágenes generadas temporalmente.
   - **Comandos en Render**:
        - `Build Command`: `pip install -r requirements.txt`
        - `Start Command`: `gunicorn app:app`
   - **Variables de Entorno**: Todas se listan en el archivo `.env`.

b. Base de Código (Control de versiones)
   - **Plataforma**: GitHub
   - **Repositorio**: `https://github.com/construex-git1/construex-ecosystem`
   - **Rama principal**: `main`
   - **Archivo principal**: `app.py`

c. Entorno de Ejecución (Lenguaje)
   - **Lenguaje**: Python 3.11.9 (definido en `runtime.txt` para Render)
   - **Entorno Virtual**: Se usa `venv` para desarrollo local.

d. Dependencias del Proyecto (`requirements.txt`)
   - El archivo `requirements.txt` en la raíz del proyecto lista todas las
     librerías de Python necesarias.
   - **Contenido principal**:
        `flask` (Servidor web),
        `requests` (Llamadas API),
        `google-generativeai` (API de Gemini),
        `beautifulsoup4` y `newspaper3k` (Extracción de contenido),
        `python-dotenv` (Gestión de variables de entorno),
        `gunicorn` (Servidor para producción en Render),
        `Pillow` (Procesamiento básico de imágenes),
        `APScheduler` (Tareas programadas),
        `feedparser` (Lectura de RSS),
        `sqlite3` (Base de datos local).

e. Configuración Secreta (`.env` - NO se sube a GitHub)
   - Contiene TODAS las claves de API y tokens sensibles.
   - Este archivo DEBE configurarse manualmente en el Dashboard de Render
     (Environment Variables). A continuación se muestra un ejemplo de su
     estructura. Los valores marcados como `{{pendiente}}` son los que aún
     faltan para que el sistema funcione al 100%.

======================================================================
4. INTEGRACIONES Y APIs
======================================================================

**EXPLICACIÓN PARA NO PROGRAMADORES**: Cada "API" es como una llave que permite
que nuestro sistema se comunique con otro servicio externo para pedirle que haga
una tarea específica (como analizar un texto o crear una imagen). La mayoría
son como cuentas de servicio gratuitas, pero algunas requieren verificación.

a. WhatsApp Business (Meta Cloud API) - **PENDIENTE DE PUBLICAR**
   - **Estado**: Cuenta verificada, número `+593 98 393 8439` agregado, pero la
     aplicación `Construex Official` en Meta Developers NO ha sido publicada.
   - **Documentación**: Revisar sección 6 de este documento.
   - **IDs Actuales**:
        - App ID: `2063982867801819`
        - Phone Number ID: `1156977064157956`
        - Verify Token (Webhook): `construex_verify_2026`
   - **Token de Acceso (Largo)**: ya se ha generado y está configurado en el
     `.env` de Render.

b. Gemini AI (Google) - **FUNCIONANDO**
   - **Función**: Analiza el texto de la noticia, la clasifica en una categoría
     y genera resúmenes y textos para las redes sociales.
   - **API Key**: `AIzaSyBTuZ2aVDO1CZgYJo93kj5I_prRjdF3ngk`
   - **Estado**: Configurada y operativa.

c. Nano Banana Pro - **FUNCIONANDO**
   - **Función**: Genera imágenes de alta calidad y estilo profesional para las
     publicaciones.
   - **API Key**: `6c660ee8fd1f9ed21d20967353828f67` (Revocar y generar nueva
     por seguridad. Ya está configurada en el `.env` de Render).
   - **Estado**: Configurada como generador principal.

d. Notion (Base de Datos)
   - **Función**: Almacena un registro de todo el contenido procesado para su
     posterior consulta.
   - **Estado**: El código la soporta, pero las variables `NOTION_API_KEY` y
     `NOTION_DATABASE_ID` están vacías en Render. El sistema funciona sin ella.
   - **Para activarla**: Conseguir un token de integración de Notion
     (https://www.notion.so/my-integrations) y el ID de una base de datos. (ya se tiene en Render)

e. Pollinations.ai - **FUNCIONANDO (RESPALDO)**
   - **Función**: Es el generador de imágenes de respaldo.
   - **Estado**: Funciona si Nano Banana falla. No requiere API key.

======================================================================
5. ESTRUCTURA DE ARCHIVOS DEL PROYECTO (`app.py`)
======================================================================

El archivo `app.py` es el corazón de la aplicación. Contiene todo el código
del flujo. A continuación, se listan sus secciones más importantes y su función.

- **Importación de Librerías y Configuración Inicial**: Carga las librerías
  y define la clase `Config` para leer las variables de entorno.

- **Funciones de Extracción y Análisis** (`extraer_noticia`, `analizar_contenido`,
  `generar_imagen`, `generar_texto_redes`): Son los "trabajadores". Cada una
  se encarga de una tarea específica (leer URL, llamar a Gemini, crear imagen).

- **Funciones de Almacenamiento** (`guardar_en_notion`, `detectar_oportunidad_lead`,
  `guardar_en_db`): Se encargan de guardar los resultados.

- **Rutas de la API** (`@app.route`): Son las "direcciones" que los servicios
  externos (como Meta) y las personas usan para interactuar con el sistema.
   - `/webhook`: La dirección que Meta usa para enviar los mensajes de WhatsApp.
   - `/`: El panel de control simple.
   - `/privacy`, `/terms`, `/data-deletion`: Páginas con la información legal.
   - `/health`: Para verificar que el servidor está funcionando.

- **Función `procesar_url_completo_sync`**: Orquesta a todos los "trabajadores".
  Es el cerebro que recibe la URL y ejecuta el flujo completo.

- **Manejador de Webhook (`handle_whatsapp`)**: La función que recibe la
  solicitud POST de Meta, extrae la URL y llama a la función orquestadora.

======================================================================
6. GUÍA DE IMPLEMENTACIÓN PARA WHATSAPP (PENDIENTE)
======================================================================

**PROBLEMA ACTUAL**: La API de WhatsApp está configurada y el webhook funciona
para números de prueba (sandbox), pero **no funciona para el número real**
`+593 98 393 8439`. Meta requiere que la aplicación `Construex Official` pase
por un proceso de revisión ("App Review") para ponerla en modo "Live".

**OBJETIVO:** Cambiar el modo de la aplicación de "Development" a "Live".

**INSTRUCCIONES PASO A PASO (Para la persona con acceso a `Construex Inc. 2`):**

1.  **Accede a Meta for Developers**:
    *   Ve a `developers.facebook.com`.
    *   Asegúrate de estar en la cuenta que tiene el portafolio empresarial
        `Construex Inc. 2`.

2.  **Selecciona la Aplicación Correcta**:
    *   En el menú superior, selecciona la aplicación **`Construex Official`**
        (ID: `2063982867801819`).

3.  **Verifica/Completa la Configuración Básica**:
    *   En el menú izquierdo, ve a **Ajustes (Settings) > Básico (Basic)**.
    *   **Asegúrate de que los siguientes campos estén COMPLETOS** (son un
        requisito de Meta para poder publicar):
        *   **URL de Política de Privacidad**:
            `https://construex-ecosystem.onrender.com/privacy`
        *   **URL de Términos de Servicio**:
            `https://construex-ecosystem.onrender.com/terms`
        *   **Icono de la aplicación**: Sube un logo.

4.  **Inicia la Revisión de la App (App Review)**:
    *   En el menú izquierdo, haz clic en **Revisión de la aplicación (App Review)**.
    *   Busca el permiso `whatsapp_business_messaging`.
    *   Haz clic en **"Solicitar Acceso Avanzado (Request Advanced Access)"**.

5.  **Completa el Formulario de Solicitud**:
    *   Selecciona el caso de uso principal: **"Customer Support"** o
        **"Utility"** (el sistema responde a preguntas/enlaces, no inicia
        conversaciones de marketing).
    *   **Proporciona un video de demostración** (¡es muy importante!): Muestra
        cómo un usuario envía una URL al número y cómo el sistema responde
        automáticamente. Usa el **número de prueba** de Meta para grabar el
        video.
    *   Explica de forma clara y concisa cómo tu aplicación usa el permiso.

6.  **Espera la Aprobación**:
    *   Una vez enviada la solicitud, Meta la revisará. Esto puede tomar desde
        un par de días hasta una semana.
    *   **Mientras la revisión está en curso, el sistema funciona sin problemas
        para los números de teléfono agregados como "Números de prueba".

7.  **Cambia el Modo a "Live"**:
    *   Una vez que la solicitud de Acceso Avanzado sea **APROBADA** por Meta,
        aparecerá un nuevo botón en la parte superior del panel de la aplicación.
    *   **Haz clic en el botón para cambiar el "App Mode" de "Development" a
        "Live".**

8.  **¡TODO LISTO!**:
    *   Después de cambiar a "Live", el webhook comenzará a recibir los mensajes
        que cualquier persona envíe al número real `+593 98 393 8439`. El sistema
        estará 100% operativo para el público.

======================================================================
7. FUNCIONALIDADES IMPLEMENTADAS (EL SISTEMA ES "INIGUALABLE")
======================================================================

El sistema ya cuenta con las siguientes capacidades, fruto de todo el desarrollo:

 **Recepción de mensajes por WhatsApp** (Pendiente de publicación en Meta).
 **Extracción de texto de cualquier artículo o noticia** vía URL.
 **Clasificación del contenido** en 5 categorías principales (Construcción,
   Emprendimiento, Salud, Educación, Innovación).
 **Generación de textos optimizados** para Instagram, Twitter, LinkedIn y
   WhatsApp.
 **Generación de imágenes profesionales** con IA (Nano Banana como opción
   principal y Pollinations como respaldo).
 **Análisis de "intención de compra" y detección de "leads"** (clientes
   potenciales).
 **Almacenamiento de todo el contenido procesado** en una base de datos local
   SQLite y en Notion (opcional).
 **Sistema de logs y monitoreo** en el servidor de Render.
 **Panel de control simple** (`/`) para ver el estado del sistema.
 **Páginas legales completas** (Política de Privacidad, Términos de Servicio,
   Eliminación de Datos).
 **Capacidad de manejar múltiples URLs simultáneamente** (usa `threading`).
 **A/B Testing de Prompts**: El sistema prueba diferentes estilos de escritura
   y aprende cuáles generan mejor "engagement".
 **Generación de Carrusel de Imágenes**: Crea múltiples diapositivas para un
   solo tema.

======================================================================
8. CHECKLIST FINAL PARA DEJAR EL SISTEMA 100% OPERATIVO
======================================================================

**PARA EL EQUIPO DE CONSTRUEX (Acceso a `Construex Inc. 2`):**

- [ ] **Completar el paso 4 (Iniciar la Revisión de la App) de la sección 6**.
      Es el único requisito pendiente para el funcionamiento público del número.

**PARA EL DESARROLLADOR (TÚ):**

- [ ] Una vez que la aplicación esté en modo "Live", no hay más pasos técnicos.
      El webhook ya está configurado correctamente.

**ESTADO DE LAS VARIABLES DE ENTORNO EN RENDER (`construex-ecosystem`):**

- [x] `GEMINI_API_KEY`: Configurada.
- [x] `WHATSAPP_PHONE_NUMBER_ID`: Configurada.
- [x] `WHATSAPP_ACCESS_TOKEN`: Configurado.
- [x] `WHATSAPP_VERIFY_TOKEN`: Configurado (`construex_verify_2026`).
- [x] `NANO_BANANA_API_KEY`: Configurada.
- [x] `NOTION_API_KEY`: Configurada.
- [x] `NOTION_DATABASE_ID`: Configurada.
- [x] `PORT`: `10000` (configurado por Render).

======================================================================
9. SOLUCIÓN DE PROBLEMAS COMUNES (TROUBLESHOOTING)
======================================================================

**Problema:** El webhook no recibe mensajes del número real.
   - **Causa más probable:** La aplicación no está en modo "Live".
   - **Solución:** Seguir la guía de la sección 6.

**Problema:** Error `404 Not Found` al acceder a `/privacy`, `/terms`, etc.
   - **Causa:** El código más reciente no se ha desplegado en Render.
   - **Solución:** Forzar un redeploy manual desde el dashboard de Render
     ("Manual Deploy" -> "Deploy latest commit").

**Problema:** La imagen no se genera.
   - **Causa:** Nano Banana puede haber fallado o agotado sus créditos diarios.
   - **Solución:** El sistema ya usa Pollinations como respaldo, por lo que la
     imagen debería generarse igual. Verificar los logs de Render para más
     detalles.

**Problema:** El análisis de Gemini es incorrecto o muy lento.
   - **Causa:** Puede ser un problema temporal de la API de Google.
   - **Solución:** Esperar y reintentar. El sistema tiene un "fallback" interno
     que asigna una categoría "por defecto" si Gemini falla.

**Problema:** Error `404 Not Found` en el comando `curl` de prueba.
   - **Causa:** El servidor de Render está activo, pero el endpoint es
     incorrecto o la aplicación no está desplegada.
   - **Solución:** Verificar que la URL del webhook en el código coincida con
     la URL de Render.

**Problema:** El número de WhatsApp `+593 98 393 8439` no verifica o no está
   disponible en la API Setup.
   - **Causa:** El número no se ha agregado correctamente a la Cuenta de
     WhatsApp Business (WABA).
   - **Solución:** Ir a `business.facebook.com`, acceder al portafolio
     `Construex Inc. 2` y al WhatsApp Manager. Allí se deben administrar los
     números de teléfono. Si no está, hay que volver a agregarlo.

======================================================================
FIN DE LA DOCUMENTACIÓN
======================================================================