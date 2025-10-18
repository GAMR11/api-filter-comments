# 🤖 Análisis de Sentimientos - Backend API

API REST desarrollada con FastAPI para análisis de sentimientos en español usando modelos de Hugging Face Transformers.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.119-green?logo=fastapi)
![Transformers](https://img.shields.io/badge/Transformers-4.57-orange)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Características

- 🧠 **IA Avanzada**: Utiliza modelo BETO (BERT en español) para análisis preciso
- 🚀 **Alto Rendimiento**: FastAPI con procesamiento asíncrono
- 📊 **Análisis por Lotes**: Procesa CSV y Excel con múltiples comentarios
- 🔒 **CORS Configurado**: Listo para consumir desde frontend
- 📝 **Documentación Automática**: Swagger UI integrado
- 🎯 **Detección Precisa**: Identifica sentimientos Positivo, Negativo y Neutral
- 🔍 **Logging Detallado**: Sistema de logs para debugging

---

## 🛠️ Tecnologías

- **FastAPI** - Framework web moderno y rápido
- **Transformers (Hugging Face)** - Modelos de IA pre-entrenados
- **PyTorch** - Backend para deep learning
- **Pandas** - Procesamiento de datos CSV/Excel
- **Pydantic** - Validación de datos
- **Uvicorn** - Servidor ASGI de alto rendimiento

---

## 🤖 Modelo de IA

### BETO Sentiment Analysis
- **Modelo**: `finiteautomata/beto-sentiment-analysis`
- **Base**: BERT (Bidirectional Encoder Representations from Transformers)
- **Idioma**: Español (España y Latinoamérica)
- **Precisión**: ~90% en dataset de prueba
- **Entrenado en**: Reviews, comentarios de redes sociales y textos variados

#### ¿Por qué BETO?
- ✅ Optimizado específicamente para español
- ✅ Detecta emociones en contexto (no solo palabras clave)
- ✅ Maneja sarcasmo y expresiones coloquiales
- ✅ Mejor que modelos multilingües genéricos

---

## 📋 Requisitos Previos

- Python 3.11 o superior
- pip 23+
- 2GB+ de RAM (para cargar el modelo)
- Conexión a internet (primera vez para descargar modelo)

---

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/GAMR11/api-filter-comments.git
cd api-filter-comments
```

### 2. Crear entorno virtual (recomendado)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

**requirements.txt:**
```txt
fastapi==0.119.0
uvicorn==0.37.0
transformers==4.57.1
torch==2.9.0
pandas==2.3.3
openpyxl==3.1.5
python-multipart==0.0.20
sentencepiece==0.2.0
```

### 4. Ejecutar el servidor

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

O directamente con Python:

```bash
python main.py
```

La API estará disponible en: `http://localhost:8000`

---

## 📚 Documentación Interactiva

Una vez que el servidor esté corriendo, accede a:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🔌 Endpoints

### 1. Raíz - Información de la API

```http
GET /
```

**Respuesta:**
```json
{
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
```

---

### 2. Health Check - Estado de la API

```http
GET /health
```

**Respuesta:**
```json
{
  "status": "healthy",
  "modelo_cargado": true,
  "modelo_nombre": "finiteautomata/beto-sentiment-analysis"
}
```

---

### 3. Analizar Comentario Individual

```http
POST /analizar
Content-Type: application/json
```

**Request Body:**
```json
{
  "comentario": "Me siento muy feliz con este servicio"
}
```

**Respuesta:**
```json
{
  "comentario": "Me siento muy feliz con este servicio",
  "etiqueta": "Positivo",
  "confianza": 95.43,
  "porcentaje_positivo": 95.43,
  "porcentaje_negativo": 4.57
}
```

---

### 4. Analizar Archivo CSV

```http
POST /analizar-csv
Content-Type: multipart/form-data
```

**Request:**
- File: archivo.csv (debe tener columna "comentario" o "texto")

**Respuesta:**
```json
{
  "total_comentarios": 100,
  "porcentaje_positivo_general": 65.0,
  "porcentaje_negativo_general": 25.0,
  "porcentaje_neutral": 10.0,
  "comentarios_analizados": [
    {
      "comentario": "Excelente producto",
      "etiqueta": "Positivo",
      "confianza": 98.5,
      "porcentaje_positivo": 98.5,
      "porcentaje_negativo": 1.5
    },
    // ... más comentarios
  ]
}
```

---

### 5. Analizar Archivo Excel

```http
POST /analizar-excel
Content-Type: multipart/form-data
```

**Request:**
- File: archivo.xlsx o archivo.xls

**Respuesta:** Misma estructura que `/analizar-csv`

---

## 📊 Formato de Archivos

### CSV
```csv
comentario
Este producto es excelente
El servicio fue malo
Precio justo
```

### Excel
| comentario |
|------------|
| Este producto es excelente |
| El servicio fue malo |
| Precio justo |

**Importante:**
- La columna puede llamarse: `comentario`, `comentarios`, `texto`, `comment` o `text`
- Tamaño máximo: 10MB
- Encoding: UTF-8 (recomendado para CSV)

---

## 🔧 Configuración

### Cambiar Puerto

```python
# En main.py
uvicorn.run(app, host="0.0.0.0", port=8000)  # Cambiar puerto aquí
```

### Configurar CORS

```python
# Agregar más orígenes permitidos
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://tu-dominio.com"
]
```

### Cambiar Modelo de IA

```python
# En main.py, función load_model()
sentiment_analyzer = pipeline(
    "sentiment-analysis",
    model="pysentimiento/robertuito-sentiment-analysis"  # Otro modelo
)
```

#### Modelos Alternativos:
- `pysentimiento/robertuito-sentiment-analysis` - Para español latinoamericano
- `cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual` - Multilingüe

---

## 🎯 Casos de Uso

### Ejemplo 1: Análisis de Reseñas de Productos

```bash
curl -X POST "http://localhost:8000/analizar" \
  -H "Content-Type: application/json" \
  -d '{"comentario": "El producto llegó rápido y en perfecto estado"}'
```

### Ejemplo 2: Monitoreo de Redes Sociales

```bash
curl -X POST "http://localhost:8000/analizar-csv" \
  -F "file=@tweets.csv"
```

### Ejemplo 3: Análisis de Encuestas

```bash
curl -X POST "http://localhost:8000/analizar-excel" \
  -F "file=@encuesta_satisfaccion.xlsx"
```

---

## 📈 Rendimiento

| Métrica | Valor |
|---------|-------|
| Tiempo de carga del modelo | ~15 segundos |
| Análisis por comentario | ~100ms |
| Requests por segundo | ~50 RPS |
| Memoria RAM requerida | ~2GB |

---

## 🐛 Solución de Problemas

### Error: "Modelo no disponible"

```bash
# Verifica conexión a internet y vuelve a instalar
pip install --upgrade transformers torch
```

### Error: CORS

```python
# Asegúrate de que el origen de tu frontend esté en la lista
origins = [
    "http://localhost:5173",  # Agrega aquí tu frontend
]
```

### Error: Archivo muy grande

El límite por defecto es 10MB. Para cambiarlo:

```python
# En main.py
FILE_CONFIG = {
    "MAX_SIZE_MB": 50  # Aumenta el límite
}
```

### Error de memoria

Si el servidor se queda sin memoria:

```bash
# Usa un modelo más ligero
model="distilbert-base-multilingual-cased"
```

---

## 🧪 Testing

### Prueba Manual con cURL

```bash
# Health check
curl http://localhost:8000/health

# Analizar comentario
curl -X POST http://localhost:8000/analizar \
  -H "Content-Type: application/json" \
  -d '{"comentario": "Estoy muy feliz"}'
```

### Prueba con Python

```python
import requests

response = requests.post(
    "http://localhost:8000/analizar",
    json={"comentario": "Me encanta este servicio"}
)
print(response.json())
```

---

## 📦 Deploy

### Docker (Recomendado)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build y run
docker build -t sentiment-api .
docker run -p 8000:8000 sentiment-api
```

### Heroku

```bash
# Crear Procfile
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Railway / Render

Simplemente conecta tu repositorio y selecciona `main.py`

---

## 🤝 Contribuir

1. Fork el proyecto
2. Crea tu rama (`git checkout -b feature/NuevaFeature`)
3. Commit tus cambios (`git commit -m 'Add: Nueva feature'`)
4. Push a la rama (`git push origin feature/NuevaFeature`)
5. Abre un Pull Request

---

## 📝 Licencia

Este proyecto está bajo la Licencia MIT. Ver `LICENSE` para más detalles.

---

## 👨‍💻 Autor

**Gustavo Morales**
- GitHub: [@GAMR11](https://github.com/GAMR11)
- LinkedIn: [https://www.linkedin.com/in/gustavo-morales-640259221](https://www.linkedin.com/in/gustavo-morales-640259221)

---

## 🙏 Agradecimientos

- [Hugging Face](https://huggingface.co/) por los modelos pre-entrenados
- [FastAPI](https://fastapi.tiangolo.com/) por el increíble framework
- Comunidad de [PyTorch](https://pytorch.org/) por las herramientas de ML

---

## 🔗 Enlaces Relacionados

- [Repositorio Frontend](https://github.com/GAMR11/frontend-filter-comments)
- [Documentación BETO](https://huggingface.co/finiteautomata/beto-sentiment-analysis)
- [FastAPI Docs](https://fastapi.tiangolo.com/)

---

**Desarrollado con 💜 | 2025**