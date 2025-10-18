from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
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
#     CONFIGURACIÓN DE FASTAPI y CORS
# ----------------------------------------------------

app = FastAPI(
    title="API de Análisis de Sentimientos",
    description="API para analizar sentimientos en comentarios usando Hugging Face",
    version="2.0.0"
)

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------
#     MODELO Y LÓGICA DE NEGOCIO
# ----------------------------------------------------

sentiment_analyzer = None

@app.on_event("startup")
async def load_model():
    """Carga el modelo al iniciar la API"""
    global sentiment_analyzer
    try:
        logger.info("Cargando modelo de análisis de sentimientos...")
        
        # Usamos modelo BETO especializado para comentarios formales e informales en español.
        sentiment_analyzer = pipeline(
            "sentiment-analysis",
            model="finiteautomata/beto-sentiment-analysis"
        )
        
        # OPCIÓN 2: Si prefieres otro modelo, descomenta:
        # sentiment_analyzer = pipeline(
        #     "sentiment-analysis",
        #     model="cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual"
        # )
        
        logger.info("✅ Modelo cargado exitosamente")
    except Exception as e:
        logger.error(f"❌ Error al cargar el modelo: {e}")
        logger.info("Intenta instalar: pip install pysentimiento")

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
    modelo_cargado: bool
    modelo_nombre: str

def analizar_sentimiento(texto: str) -> Dict:
    """
    Analiza el sentimiento de un texto usando el modelo mejorado
    """
    if sentiment_analyzer is None:
        logger.warning("Modelo no disponible.")
        return {
            "comentario": texto,
            "etiqueta": "Neutral",
            "confianza": 50.0,
            "porcentaje_positivo": 50.0,
            "porcentaje_negativo": 50.0
        }

    try:
        # Limitar a 512 caracteres
        resultado = sentiment_analyzer(texto[:512])[0]
        
        label = resultado['label'].upper()
        score = resultado['score']
        
        # Mapeo de etiquetas del modelo BETO
        # El modelo retorna: POS, NEG, NEU
        if label in ['POS', 'POSITIVE']:
            sentimiento = "Positivo"
            porcentaje_positivo = score * 100
            porcentaje_negativo = (1 - score) * 100
        elif label in ['NEG', 'NEGATIVE']:
            sentimiento = "Negativo"
            porcentaje_negativo = score * 100
            porcentaje_positivo = (1 - score) * 100
        else:  # NEU, NEUTRAL
            sentimiento = "Neutral"
            # Para neutral, distribuimos más equitativamente
            porcentaje_positivo = 50.0
            porcentaje_negativo = 50.0
            score = 0.5  # Ajustamos la confianza para neutral
        
        return {
            "comentario": texto,
            "etiqueta": sentimiento,
            "confianza": round(score * 100, 2),
            "porcentaje_positivo": round(porcentaje_positivo, 2),
            "porcentaje_negativo": round(porcentaje_negativo, 2)
        }
    
    except Exception as e:
        logger.error(f"Error en análisis: {e}")
        # Fallback en caso de error
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
        "mensaje": "API de Análisis de Sentimientos v2.0",
        "version": "2.0.0",
        "modelo": "BETO Sentiment Analysis (español)",
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
    return {
        "status": "healthy" if sentiment_analyzer is not None else "degraded",
        "modelo_cargado": sentiment_analyzer is not None,
        "modelo_nombre": "finiteautomata/beto-sentiment-analysis"
    }

@app.post("/analizar", response_model=SentimentResult)
async def analizar_comentario(request: CommentRequest):
    """Analiza un solo comentario"""
    try:
        if not request.comentario.strip():
            raise HTTPException(status_code=400, detail="El comentario no puede estar vacío")
        
        resultado = analizar_sentimiento(request.comentario)
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
        
        # Buscar columna de comentarios
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
        
        # Procesar comentarios
        resultados = []
        for comentario in df[columna_comentarios].dropna():
            if str(comentario).strip():  # Validar que no esté vacío
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
    """Analiza múltiples comentarios desde un archivo Excel"""
    try:
        if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
            raise HTTPException(status_code=400, detail="El archivo debe ser Excel (.xlsx o .xls)")
        
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        # Buscar columna de comentarios
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
        
        # Procesar comentarios
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)