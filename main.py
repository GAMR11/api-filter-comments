from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import pipeline
import pandas as pd
import io
import os
import requests
from typing import List, Dict
import logging
from dotenv import load_dotenv
load_dotenv()
from services.firebase_service import firebase_service
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------------------------------
#     CONFIGURACIÓN DE FASTAPI y CORS
# ----------------------------------------------------

app = FastAPI(
    title="API de Análisis de Sentimientos",
    description="API para analizar sentimientos en comentarios usando Hugging Face",
    version="2.1.0"
)

origins = [
    # "http://localhost:5173",
    # "http://127.0.0.1:5173",
    "https://*.vercel.app",
    "https://*.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------
#     CONFIGURACIÓN DE HUGGING FACE API
# ----------------------------------------------------

HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")
HF_MODEL = "finiteautomata/beto-sentiment-analysis"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

# ----------------------------------------------------
#     STARTUP: INICIALIZAR FIREBASE
# ----------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """Inicializa Firebase al arrancar la aplicación"""
    logger.info("🚀 Iniciando aplicación...")
    
    # Inicializar Firebase
    firebase_service.initialize()
    
    logger.info("✅ Aplicación lista")

# ----------------------------------------------------
#     MODELOS PYDANTIC
# ----------------------------------------------------

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
    firebase_connected: bool
    hf_api_configured: bool
    environment: str

class StatisticsResponse(BaseModel):
    total_analisis_individuales: int
    total_analisis_batch: int
    total_general: int

# ----------------------------------------------------
#     FUNCIÓN DE ANÁLISIS
# ----------------------------------------------------

def analizar_sentimiento(texto: str) -> Dict:
    """Analiza el sentimiento usando Hugging Face API"""
    try:
        headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
        payload = {"inputs": texto[:512]}
        
        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            resultado = response.json()[0][0]  
            
            label = resultado['label'].upper()
            score = resultado['score']
            
            if label in ['POS', 'POSITIVE']:
                sentimiento = "Positivo"
                porcentaje_positivo = score * 100
                porcentaje_negativo = (1 - score) * 100
            elif label in ['NEG', 'NEGATIVE']:
                sentimiento = "Negativo"
                porcentaje_negativo = score * 100
                porcentaje_positivo = (1 - score) * 100
            else:
                sentimiento = "Neutral"
                porcentaje_positivo = 50.0
                porcentaje_negativo = 50.0
                score = 0.5
            
            return {
                "comentario": texto,
                "etiqueta": sentimiento,
                "confianza": round(score * 100, 2),
                "porcentaje_positivo": round(porcentaje_positivo, 2),
                "porcentaje_negativo": round(porcentaje_negativo, 2)
            }
        else:
            logger.error(f"Error de HF API: {response.status_code} - {response.text}")
            raise Exception("Error en la API de Hugging Face")
    
    except Exception as e:
        logger.error(f"Error en análisis: {e}")
        # Fallback
        return {
            "comentario": texto,
            "etiqueta": "Neutral",
            "confianza": 50.0,
            "porcentaje_positivo": 50.0,
            "porcentaje_negativo": 50.0
        }

# ----------------------------------------------------
#     ENDPOINTS
# ----------------------------------------------------

@app.get("/")
async def root():
    """Endpoint de bienvenida"""
    return {
        "mensaje": "API de Análisis de Sentimientos v2.1",
        "version": "2.1.0",
        "modelo": "BETO via Hugging Face API",
        "firebase": "Almacenamiento activo" if firebase_service.initialized else "No configurado",
        "status": "online",
        "endpoints": {
            "analizar_comentario": "/analizar",
            "analizar_csv": "/analizar-csv",
            "analizar_excel": "/analizar-excel",
            "estadisticas": "/statistics",
            "salud": "/health"
        }
    }

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Verifica el estado de la API"""
    return {
        "status": "healthy",
        "firebase_connected": firebase_service.initialized,
        "hf_api_configured": bool(HF_API_TOKEN),
        "environment": os.getenv("RENDER", "local")
    }

@app.get("/statistics", response_model=StatisticsResponse)
async def get_statistics():
    """Obtiene estadísticas de uso"""
    stats = firebase_service.get_statistics()
    return stats

@app.post("/analizar", response_model=SentimentResult)
async def analizar_comentario(request: CommentRequest):
    """Analiza un solo comentario"""
    try:
        if not request.comentario.strip():
            raise HTTPException(status_code=400, detail="El comentario no puede estar vacío")
        
        resultado = analizar_sentimiento(request.comentario)
        
        firebase_service.save_single_analysis(request.comentario, resultado)
        
        return resultado
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al analizar comentario: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")

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
                detail=f"No se encontró columna válida. Columnas: {list(df.columns)}"
            )
        
        resultados = []
        for comentario in df[columna_comentarios].dropna():
            if str(comentario).strip():
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
        
        resultado_final = {
            "total_comentarios": total,
            "porcentaje_positivo_general": round((positivos / total) * 100, 2),
            "porcentaje_negativo_general": round((negativos / total) * 100, 2),
            "porcentaje_neutral": round((neutrales / total) * 100, 2),
            "comentarios_analizados": resultados
        }
        
        firebase_service.save_batch_analysis(
            filename=file.filename,
            total_comentarios=total,
            porcentaje_positivo=resultado_final["porcentaje_positivo_general"],
            porcentaje_negativo=resultado_final["porcentaje_negativo_general"],
            porcentaje_neutral=resultado_final["porcentaje_neutral"],
            comentarios=resultados
        )
        
        return resultado_final
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al procesar CSV: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/analizar-excel", response_model=BatchSentimentResult)
async def analizar_excel(file: UploadFile = File(...)):
    """Analiza múltiples comentarios desde un archivo Excel"""
    try:
        if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
            raise HTTPException(status_code=400, detail="El archivo debe ser Excel")
        
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
                detail=f"No se encontró columna válida. Columnas: {list(df.columns)}"
            )
        
        resultados = []
        for comentario in df[columna_comentarios].dropna():
            if str(comentario).strip():
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
        
        resultado_final = {
            "total_comentarios": total,
            "porcentaje_positivo_general": round((positivos / total) * 100, 2),
            "porcentaje_negativo_general": round((negativos / total) * 100, 2),
            "porcentaje_neutral": round((neutrales / total) * 100, 2),
            "comentarios_analizados": resultados
        }
        
        firebase_service.save_batch_analysis(
            filename=file.filename,
            total_comentarios=total,
            porcentaje_positivo=resultado_final["porcentaje_positivo_general"],
            porcentaje_negativo=resultado_final["porcentaje_negativo_general"],
            porcentaje_neutral=resultado_final["porcentaje_neutral"],
            comentarios=resultados
        )
        
        return resultado_final
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al procesar Excel: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)