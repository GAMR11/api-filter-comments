from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import io
import os
import requests
from typing import List, Dict
import logging
from dotenv import load_dotenv

# ----------------------------------------------------
# 🟢 CARGAR VARIABLES DE ENTORNO
# ----------------------------------------------------

# Esto busca y carga las variables del archivo .env en el directorio actual
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------------------------------
#               CONFIGURACIÓN GLOBAL
# ----------------------------------------------------

# Token de Hugging Face, cargado desde la variable de entorno HF_API_TOKEN
# ¡Asegúrate de configurar esta variable en tu entorno (ej. Railway/Render)!
HF_API_TOKEN = os.getenv("HF_API_TOKEN") 
HF_MODEL = "finiteautomata/beto-sentiment-analysis"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

if not HF_API_TOKEN:
    logger.error("La variable de entorno HF_API_TOKEN no está configurada.")
    
# ----------------------------------------------------
#  CONFIGURACIÓN DE FASTAPI y CORS
# ----------------------------------------------------

app = FastAPI(
 title="API de Análisis de Sentimientos",
 description="API para analizar sentimientos en comentarios usando Hugging Face Inference API",
 version="2.0.0"
)


origins = [
    # "http://localhost:5173",
    # "http://127.0.0.1:5173",
    # "http://127.0.0.1:8000",
    "frontend-filter-comments-r9i629d7w.vercel.app",
    "https://frontend-filter-comments.vercel.app",
    "https://*.vercel.app",
]

app.add_middleware(
 CORSMiddleware,
 allow_origins=origins,
 allow_credentials=True,
 allow_methods=["*"],
 allow_headers=["*"],
)

# ----------------------------------------------------
#  MODELOS PYDANTIC Y LÓGICA DE NEGOCIO
# ----------------------------------------------------

# Modelos Pydantic
class CommentRequest(BaseModel):
    comentario: str

class SentimentResult(BaseModel):
 comentario: str
 etiqueta: str
 confianza: float
 porcentaje_positivo: float
 porcentaje_negativo: float

class BatchSentimentResult(BaseModel):
 total_comentarios: int
 porcentaje_positivo_general: float
 porcentaje_negativo_general: float
 porcentaje_neutral: float
 comentarios_analizados: List[SentimentResult]

class HealthCheckResponse(BaseModel):
 status: str
 modelo_disponible: bool # Cambiamos a 'disponible' en lugar de 'cargado'
 modelo_nombre: str
 environment: str


def analizar_sentimiento(texto: str) -> Dict:
    """Analiza el sentimiento de un texto usando la Hugging Face Inference API"""
    
    # 1. Verificar el token antes de la solicitud
    if not HF_API_TOKEN:
        logger.error("Token HF no disponible para análisis.")
        raise HTTPException(status_code=503, detail="Servicio de inferencia no disponible (Token no configurado)")
    
    # 2. Configurar la solicitud
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    # La API de inferencia solo soporta texto hasta 512 tokens. Recortamos a 512 caracteres para seguridad.
    payload = {"inputs": texto[:512]} 
    
    try:
        # 3. Llamar a la API de Hugging Face
        response = requests.post(
            HF_API_URL,
            headers=headers,
            json=payload
        )

        # 4. Manejar posibles errores de la API
        if response.status_code != 200:
            logger.error(f"Error de la API HF ({response.status_code}): {response.text}")
            # Lanzamos una HTTPException para que FastAPI la maneje
            raise HTTPException(
                status_code=response.status_code, 
                detail=f"Error en la API de Hugging Face: {response.text}"
            )

        # 5. Procesar el resultado (asumiendo formato BETO: [{"label": "POS", "score": 0.99}, ...])
        resultado = response.json()[0][0] # La API retorna una lista de listas: [[...]]
        
        label = resultado['label'].upper()
        score = resultado['score']
        
        # 6. Mapear etiquetas y calcular porcentajes
        if label in ['POS', 'POSITIVE']:
            sentimiento = "Positivo"
            # Asumimos que el score es la confianza en la etiqueta predicha
            porcentaje_positivo = score * 100
            porcentaje_negativo = (1 - score) * 100
        elif label in ['NEG', 'NEGATIVE']:
            sentimiento = "Negativo"
            porcentaje_negativo = score * 100
            porcentaje_positivo = (1 - score) * 100
        else:
            # Manejo de etiquetas inesperadas o neutral (si el modelo lo soporta)
            sentimiento = "Neutral"
            score = 0.5 # Asumimos 50% para neutral si el modelo no da un score claro
            porcentaje_positivo = 50.0
            porcentaje_negativo = 50.0
        
        return {
            "comentario": texto,
            "etiqueta": sentimiento,
            "confianza": round(score * 100, 2),
            "porcentaje_positivo": round(porcentaje_positivo, 2),
            "porcentaje_negativo": round(porcentaje_negativo, 2)
        }
    
    except HTTPException:
        raise # Relanzar la excepción HTTP ya creada
    except Exception as e:
        logger.error(f"Error en análisis por API: {e}")
        # Retornar un error 500 si falla la conexión o el procesamiento
        raise HTTPException(status_code=500, detail=f"Error al conectar con el servicio de inferencia: {str(e)}")


# ----------------------------------------------------
#  ENDPOINTS
# ----------------------------------------------------

@app.get("/")
async def root():
 """Endpoint de bienvenida"""
 return {
  "mensaje": "API de Análisis de Sentimientos v2.0 (Hugging Face Inference API)",
  "version": "2.0.0",
  "modelo": "BETO Sentiment Analysis (español)",
  "status": "online",
  "endpoints": {
   "analizar_comentario": "/analizar",
   "analizar_csv": "/analizar-csv",
   "analizar_excel": "/analizar-excel",
   "documentacion": "/docs",
   "salud": "/health"
  }
 }

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
 """Verifica el estado de la API"""
 # El estado del modelo ahora depende de si el token está presente
 return {
  "status": "healthy" if HF_API_TOKEN else "degraded",
  "modelo_disponible": bool(HF_API_TOKEN),
  "modelo_nombre": HF_MODEL,
  "environment": os.getenv("RENDER", "local") # Usé RENDER, puedes usar RAILWAY o el que aplique
 }

@app.post("/analizar", response_model=SentimentResult)
async def analizar_comentario(request: CommentRequest):
 """Analiza un solo comentario"""
 try:
  if not request.comentario.strip():
   raise HTTPException(status_code=400, detail="El comentario no puede estar vacío")
  
  # analizar_sentimiento ahora lanza HTTPException en caso de error
  resultado = analizar_sentimiento(request.comentario) 
  return resultado
 
 except HTTPException:
  raise
 except Exception as e:
  logger.error(f"Error inesperado al analizar comentario: {e}")
  raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")

# Los endpoints /analizar-csv y /analizar-excel permanecen iguales
# ya que llaman a la función analizar_sentimiento

@app.post("/analizar-csv", response_model=BatchSentimentResult)
async def analizar_csv(file: UploadFile = File(...)):
    # ... (código /analizar-csv) ...
    try:
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="El archivo debe ser CSV")
        
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        
        columna_comentarios = None
        for col in ['comentario', 'comentarios', 'texto', 'comment', 'text']:
            if col in df.columns:
                columna_comentarios = col
                break
        
        if columna_comentarios is None:
            raise HTTPException(
                status_code=400,
                detail=f"No se encontró columna válida. Columnas disponibles: {list(df.columns)}"
            )
        
        resultados = []
        for comentario in df[columna_comentarios].dropna():
            if str(comentario).strip():
                # El manejo de errores ahora está dentro de analizar_sentimiento, 
                # así que los errores del API se propagarán como HTTPException
                try:
                    resultado = analizar_sentimiento(str(comentario))
                    resultados.append(resultado)
                except HTTPException as http_exc:
                    # Opcional: registrar error pero seguir con el siguiente (depende de la política de negocio)
                    logger.warning(f"Omitiendo comentario por error del API: {http_exc.detail}")
                    continue 
        
        total = len(resultados)
        if total == 0:
            return BatchSentimentResult(
                total_comentarios=0,
                porcentaje_positivo_general=0.0,
                porcentaje_negativo_general=0.0,
                porcentaje_neutral=100.0,
                comentarios_analizados=[]
            )

        positivos = sum(1 for r in resultados if r['etiqueta'] == 'Positivo')
        negativos = sum(1 for r in resultados if r['etiqueta'] == 'Negativo')
        neutrales = sum(1 for r in resultados if r['etiqueta'] == 'Neutral')
        
        return {
            "total_comentarios": total,
            "porcentaje_positivo_general": round((positivos / total) * 100, 2),
            "porcentaje_negativo_general": round((negativos / total) * 100, 2),
            "porcentaje_neutral": round((neutrales / total) * 100, 2),
            "comentarios_analizados": resultados
        }
    
    except HTTPException:
        raise
    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="El archivo CSV está vacío")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Error de codificación. Asegúrate de que el CSV esté en UTF-8")
    except Exception as e:
        logger.error(f"Error al procesar CSV: {e}")
        raise HTTPException(status_code=500, detail=f"Error al procesar archivo: {str(e)}")

@app.post("/analizar-excel", response_model=BatchSentimentResult)
async def analizar_excel(file: UploadFile = File(...)):
    # ... (código /analizar-excel) ...
    try:
        if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
            raise HTTPException(status_code=400, detail="El archivo debe ser Excel (.xlsx o .xls)")
        
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        columna_comentarios = None
        for col in ['comentario', 'comentarios', 'texto', 'comment', 'text']:
            if col in df.columns:
                columna_comentarios = col
                break
        
        if columna_comentarios is None:
            raise HTTPException(
                status_code=400,
                detail=f"No se encontró columna válida. Columnas disponibles: {list(df.columns)}"
            )
        
        resultados = []
        for comentario in df[columna_comentarios].dropna():
            if str(comentario).strip():
                # El manejo de errores ahora está dentro de analizar_sentimiento, 
                # así que los errores del API se propagarán como HTTPException
                try:
                    resultado = analizar_sentimiento(str(comentario))
                    resultados.append(resultado)
                except HTTPException as http_exc:
                    logger.warning(f"Omitiendo comentario por error del API: {http_exc.detail}")
                    continue 

        total = len(resultados)
        if total == 0:
            return BatchSentimentResult(
                total_comentarios=0,
                porcentaje_positivo_general=0.0,
                porcentaje_negativo_general=0.0,
                porcentaje_neutral=100.0,
                comentarios_analizados=[]
            )
            
        positivos = sum(1 for r in resultados if r['etiqueta'] == 'Positivo')
        negativos = sum(1 for r in resultados if r['etiqueta'] == 'Negativo')
        neutrales = sum(1 for r in resultados if r['etiqueta'] == 'Neutral')
        
        return {
            "total_comentarios": total,
            "porcentaje_positivo_general": round((positivos / total) * 100, 2),
            "porcentaje_negativo_general": round((negativos / total) * 100, 2),
            "porcentaje_neutral": round((neutrales / total) * 100, 2),
            "comentarios_analizados": resultados
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al procesar Excel: {e}")
        raise HTTPException(status_code=500, detail=f"Error al procesar archivo: {str(e)}")

# Para Render: obtener puerto de variable de entorno
if __name__ == "__main__":
 import uvicorn
 port = int(os.getenv("PORT", 8000))
 uvicorn.run(app, host="0.0.0.0", port=port)