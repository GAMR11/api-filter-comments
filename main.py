from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from transformers import pipeline
import pandas as pd
import io
from typing import List, Dict
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar FastAPI
app = FastAPI(
    title="API de Análisis de Sentimientos",
    description="API para analizar sentimientos en comentarios usando Hugging Face",
    version="1.0.0"
)

# Modelo de sentimientos en español (carga al iniciar)
# Usando un modelo optimizado para español
sentiment_analyzer = None

@app.on_event("startup")
async def load_model():
    """Carga el modelo al iniciar la API"""
    global sentiment_analyzer
    try:
        logger.info("Cargando modelo de análisis de sentimientos...")
        # Modelo en español de Hugging Face
        sentiment_analyzer = pipeline(
            "sentiment-analysis",
            model="nlptown/bert-base-multilingual-uncased-sentiment"
        )
        logger.info("Modelo cargado exitosamente")
    except Exception as e:
        logger.error(f"Error al cargar el modelo: {e}")
        raise

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

def analizar_sentimiento(texto: str) -> Dict:
    """
    Analiza el sentimiento de un texto
    El modelo retorna estrellas (1-5), donde:
    1-2 estrellas = Negativo
    3 estrellas = Neutral
    4-5 estrellas = Positivo
    """
    resultado = sentiment_analyzer(texto[:512])[0]  # Limitar a 512 caracteres
    
    # Mapear estrellas a sentimiento
    label = resultado['label']
    score = resultado['score']
    
    # Convertir estrellas a porcentajes
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

@app.get("/")
async def root():
    """Endpoint de bienvenida"""
    return {
        "mensaje": "API de Análisis de Sentimientos",
        "version": "1.0.0",
        "endpoints": {
            "analizar_comentario": "/analizar",
            "analizar_csv": "/analizar-csv",
            "analizar_excel": "/analizar-excel",
            "documentacion": "/docs"
        }
    }

@app.post("/analizar", response_model=SentimentResult)
async def analizar_comentario(request: CommentRequest):
    """
    Analiza un solo comentario
    
    Ejemplo de uso:
    POST /analizar
    {
        "comentario": "Este producto es excelente, me encanta!"
    }
    """
    try:
        if not request.comentario.strip():
            raise HTTPException(status_code=400, detail="El comentario no puede estar vacío")
        
        resultado = analizar_sentimiento(request.comentario)
        return resultado
    
    except Exception as e:
        logger.error(f"Error al analizar comentario: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analizar-csv", response_model=BatchSentimentResult)
async def analizar_csv(file: UploadFile = File(...)):
    """
    Analiza múltiples comentarios desde un archivo CSV
    
    El CSV debe tener una columna llamada 'comentario' o 'texto'
    """
    try:
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="El archivo debe ser CSV")
        
        # Leer CSV
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
                detail="No se encontró columna 'comentario' o 'texto' en el CSV"
            )
        
        # Analizar cada comentario
        resultados = []
        for comentario in df[columna_comentarios].dropna():
            resultado = analizar_sentimiento(str(comentario))
            resultados.append(resultado)
        
        # Calcular estadísticas generales
        total = len(resultados)
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
        raise HTTPException(status_code=400, detail="El archivo CSV está vacío")
    except Exception as e:
        logger.error(f"Error al procesar CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analizar-excel", response_model=BatchSentimentResult)
async def analizar_excel(file: UploadFile = File(...)):
    """
    Analiza múltiples comentarios desde un archivo Excel
    
    El Excel debe tener una columna llamada 'comentario' o 'texto'
    """
    try:
        if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
            raise HTTPException(status_code=400, detail="El archivo debe ser Excel (.xlsx o .xls)")
        
        # Leer Excel
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
                detail="No se encontró columna 'comentario' o 'texto' en el Excel"
            )
        
        # Analizar cada comentario
        resultados = []
        for comentario in df[columna_comentarios].dropna():
            resultado = analizar_sentimiento(str(comentario))
            resultados.append(resultado)
        
        # Calcular estadísticas generales
        total = len(resultados)
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
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Verifica el estado de la API"""
    return {
        "status": "healthy",
        "modelo_cargado": sentiment_analyzer is not None
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)