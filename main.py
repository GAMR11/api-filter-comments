from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware # 👈 Importación de CORS
from pydantic import BaseModel
from transformers import pipeline
import pandas as pd
import io
from typing import List, Dict
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------------------------------
#     CONFIGURACIÓN DE FASTAPI y CORS
# ----------------------------------------------------

# Inicializar FastAPI
app = FastAPI(
    title="API de Análisis de Sentimientos",
    description="API para analizar sentimientos en comentarios usando Hugging Face",
    version="1.0.0"
)

# Definir los orígenes permitidos.
# IMPORTANTE: Reemplaza o añade el puerto de tu frontend de React (ej. 3000, 5173).
origins = [
    "http://localhost",
    "http://localhost:3000",# Origen común de React (Create React App)
    "http://localhost:5173",# Origen común de React (Vite)
    "http://127.0.0.1:8000",# Tu propio backend
    # "https://tu-dominio-frontend.com" # Si lo despliegas
]

# Agregar el middleware de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Lista de orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"], # Permite todos los métodos (GET, POST, etc.)
    allow_headers=["*"], # Permite todos los headers
)

# ----------------------------------------------------
#     MODELO Y LÓGICA DE NEGOCIO
# ----------------------------------------------------

# Modelo de sentimientos en español (carga al iniciar)
sentiment_analyzer = None

@app.on_event("startup")
async def load_model():
    """Carga el modelo al iniciar la API"""
    global sentiment_analyzer
    try:
        logger.info("Cargando modelo de análisis de sentimientos...")
        sentiment_analyzer = pipeline(
            "sentiment-analysis",
            model="nlptown/bert-base-multilingual-uncased-sentiment"
        )
        logger.info("Modelo cargado exitosamente")
    except Exception as e:
        logger.error(f"Error al cargar el modelo: {e}")
        # Es mejor no levantar la excepción para permitir que la API arranque si el modelo falla
        # pero para el contexto de este ejercicio, la mantenemos como está.
        # raise

# Modelos Pydantic para request/response
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

class HealthCheckResponse(BaseModel): # 👈 Agregamos el Pydantic Model para Health Check
    status: str
    modelo_cargado: bool

def analizar_sentimiento(texto: str) -> Dict:
    """
    Analiza el sentimiento de un texto y mapea las 1-5 estrellas a etiquetas (Positivo, Negativo, Neutral)
    """
    # Manejo de casos donde sentiment_analyzer no pudo cargar
    if sentiment_analyzer is None:
         logger.warning("Modelo no disponible, retornando resultado dummy.")
         return {
            "comentario": texto,
            "etiqueta": "Neutral",
            "confianza": 50.0,
            "porcentaje_positivo": 50.0,
            "porcentaje_negativo": 50.0
         }

    # Limitar a 512 caracteres para el modelo
    resultado = sentiment_analyzer(texto[:512])[0]
    
    label = resultado['label']
    score = resultado['score']
    
    # Lógica de mapeo
    if '1 star' in label or '2 stars' in label:
        sentimiento = "Negativo"
        porcentaje_negativo = score * 100
        porcentaje_positivo = (1 - score) * 100
    elif '4 stars' in label or '5 stars' in label:
        sentimiento = "Positivo"
        porcentaje_positivo = score * 100
        porcentaje_negativo = (1 - score) * 100
    else:
        sentimiento = "Neutral"
        porcentaje_positivo = 50.0
        porcentaje_negativo = 50.0
    
    return {
        "comentario": texto,
        "etiqueta": sentimiento,
        "confianza": round(score * 100, 2),
        "porcentaje_positivo": round(porcentaje_positivo, 2),
        "porcentaje_negativo": round(porcentaje_negativo, 2)
    }

# ----------------------------------------------------
#     ENDPOINTS
# ----------------------------------------------------

@app.get("/")
async def root():
    """Endpoint de bienvenida"""
    return {
        "mensaje": "API de Análisis de Sentimientos",
        "version": "1.0.0",
        "endpoints": {
            "analizar_comentario": "/analizar",
            "analizar_csv": "/analizar-csv",
            "documentacion": "/docs",
            "salud": "/health"
        }
    }

@app.get("/health", response_model=HealthCheckResponse) # 👈 Añadido response_model
async def health_check():
    """Verifica el estado de la API, esencial para el frontend."""
    return {
        "status": "healthy",
        "modelo_cargado": sentiment_analyzer is not None
    }

@app.post("/analizar", response_model=SentimentResult)
async def analizar_comentario(request: CommentRequest):
    """Analiza un solo comentario"""
    try:
        if not request.comentario.strip():
            raise HTTPException(status_code=400, detail="El comentario no puede estar vacío")
        
        resultado = analizar_sentimiento(request.comentario)
        return resultado
    
    except Exception as e:
        logger.error(f"Error al analizar comentario: {e}")
        # Retorna el error 500 para debug.
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")

@app.post("/analizar-csv", response_model=BatchSentimentResult)
async def analizar_csv(file: UploadFile = File(...)):
    """Analiza múltiples comentarios desde un archivo CSV"""
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
                detail="No se encontró columna 'comentario' o 'texto' en el CSV"
            )
        
        resultados = []
        # Solo procesar filas con contenido
        for comentario in df[columna_comentarios].dropna():
            resultado = analizar_sentimiento(str(comentario))
            resultados.append(resultado)
        
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
    
    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="El archivo CSV está vacío o no es válido")
    except Exception as e:
        logger.error(f"Error al procesar CSV: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")

@app.post("/analizar-excel", response_model=BatchSentimentResult)
async def analizar_excel(file: UploadFile = File(...)):
    """Analiza múltiples comentarios desde un archivo Excel"""
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
                detail="No se encontró columna 'comentario' o 'texto' en el Excel"
            )
        
        resultados = []
        for comentario in df[columna_comentarios].dropna():
            resultado = analizar_sentimiento(str(comentario))
            resultados.append(resultado)
        
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
    
    except Exception as e:
        logger.error(f"Error al procesar Excel: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")

if __name__ == "__main__":
    import uvicorn
    # Se usa 0.0.0.0 para que sea accesible desde el exterior del contenedor/entorno,
    # pero sigue accesible como localhost:8000 desde tu máquina.
    uvicorn.run(app, host="0.0.0.0", port=8000)