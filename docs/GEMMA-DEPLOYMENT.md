# Guía de Despliegue de Gemma GGUF en Azure (CPU + Llama.cpp)

Esta guía detalla los pasos para desplegar tu modelo local **Gemma GGUF (google_gemma-4-E4B-it-GGUF)** en **Azure Container Apps (ACA)** utilizando **Llama.cpp Server** con montaje en **Azure Files** y escalado a cero (Scale to Zero) para optimizar costos.

---

## Paso 1: Crear el Azure File Share

El archivo GGUF (5.8 GB) se almacenará de manera persistente en Azure Storage y se montará en el contenedor al arrancar.

1. Ve a tu cuenta de almacenamiento en el Portal de Azure (o crea una en el mismo Resource Group que tu Container Apps, ej. `rg-evangelista-prod`).
2. En la barra lateral izquierda, selecciona **recursos compartidos de archivos (File Shares)**.
3. Haz clic en **+ Recurso compartido de archivos**.
4. Nómbralo `models` y selecciona el nivel optimizado para transacciones o hot (Standard).
5. Ve a **Claves de acceso (Access Keys)** en la cuenta de almacenamiento y copia la **Cadena de conexión (Connection String)**.

---

## Paso 2: Subir los Archivos del Modelo a Azure

Para subir los archivos `.gguf` que tienes en tu carpeta local del backend hacia Azure Files, utiliza el script automatizado que hemos creado.

Desde la carpeta `Backend/`, con tu entorno virtual activo, ejecuta:

```bash
python scripts/upload_model_to_azure.py --conn-string "TU_CADENA_DE_CONEXION_AQUI"
```

El script subirá los siguientes archivos con barra de progreso interactiva de forma directa y segura a la raíz del file share `models`:
- `google_gemma-4-E4B-it-Q5_K_M.gguf` (~5.8 GB)
- `mmproj-google_gemma-4-E4B-it-f16.gguf` (~990 MB)

---

## Paso 3: Desplegar el Contenedor de Inferencia (LLM) en Azure Container Apps

Desplegaremos el servidor de inferencia de Llama.cpp de forma desacoplada para optimizar los recursos.

### 1. Vincular el File Share en Azure Container Apps Environment
Antes de crear la app del contenedor, debemos registrar el almacenamiento en el entorno de Container Apps (Managed Environment):
1. En el portal de Azure, abre tu entorno de Container Apps (`cae-evangelista`).
2. Selecciona **Almacenamiento (Storage)** en la barra lateral.
3. Haz clic en **Agregar (Add)** y asocia el Azure File Share `models` que creaste en el Paso 1. Asígnale el nombre de recurso `models-volume`.

### 2. Crear la App del Contenedor de Inferencia (`llm-server`)
1. Crea una nueva App de Contenedor dentro de tu entorno con el nombre `app-evangelista-llm`.
2. **Configuración del Contenedor:**
   - **Imagen:** `ghcr.io/ggerganov/llama.cpp:server` (Imagen oficial de Llama.cpp Server).
   - **Recursos del Contenedor (CPU/RAM):** Te sugerimos configurar al menos **4 vCPUs y 8 GB de RAM** para CPU Burstable.
   - **Montaje de Volumen:**
     - Monta el almacenamiento `models-volume` en la ruta del contenedor `/models` como **Lectura/Escritura** (o Solo Lectura).
   - **Comando de Arranque (Override Entrypoint / Command Arguments):**
     Configura los argumentos exactamente así para cargar tu modelo y optimizar el procesamiento en CPU:
     ```bash
     /llama-server --host 0.0.0.0 --port 8080 --model /models/google_gemma-4-E4B-it-Q5_K_M.gguf -c 4096 --embedding --parallel 2
     ```
3. **Ingreso de Red (Ingress):**
   - Habilita Ingress como **Interno (Limited to Container Apps Environment)**.
   - Puerto de destino: **8080**.
   - Esto generará una URL interna para que el backend se comunique con él, por ejemplo: `http://app-evangelista-llm.internal.azurewebsites.net`.

### 3. Configurar Escalado a Cero (Scale to Zero)
1. En la configuración de la app del contenedor, ve a la pestaña **Escalado (Scale)**.
2. Configura los límites de réplica:
   - **Mínimo de réplicas:** `0` (Esto apagará por completo el contenedor cuando no haya peticiones).
   - **Máximo de réplicas:** `1` (Dado que corremos en CPU, una sola instancia es suficiente para procesar secuencialmente).
3. Agrega una regla de escalado basada en peticiones concurrentes de tipo **HTTP** con valor de `10` peticiones simultáneas.

---

## Paso 4: Conectar el Backend de FastAPI a tu Gemma Local

En la configuración del contenedor del Backend (`app-evangelista-backend-19863`), establece las siguientes variables de entorno:

```env
LLM_PROVIDER=openai_generic
LLM_MODEL=gemma-local
LOCAL_LLM_URL=http://app-evangelista-llm:8080/v1
```

*(Nota: Reemplaza `app-evangelista-llm` por el nombre DNS interno real de tu contenedor de inferencia en Azure).*

Una vez configurado, el backend utilizará la API interna compatible con OpenAI provista por Llama.cpp para energizar a la agente Evangeline y todos los procesos de RAG.
