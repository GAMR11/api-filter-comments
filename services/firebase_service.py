import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from typing import Dict, List, Optional
import logging
import os

logger = logging.getLogger(__name__)

class FirebaseService:
    """Servicio para gestionar operaciones con Firestore"""
    
    def __init__(self):
        self.db = None
        self.initialized = False
        
    def initialize(self):
        """Inicializa la conexión con Firebase"""
        try:
            # Verificar si ya está inicializado
            if self.initialized:
                return

            cred = None
            
            # --- NUEVA OPCIÓN 1: Usar variable de entorno con JSON (Estándar en la Nube) ---
            # Las plataformas de hosting a menudo requieren que el JSON sea una sola cadena.
            cred_json_str = os.getenv("FIREBASE_CREDENTIALS_JSON") 
            if cred_json_str:
                # Cargar el JSON desde la variable de entorno
                import json
                cred_info = json.loads(cred_json_str)
                cred = credentials.Certificate(cred_info)
                logger.info("✅ Usando credenciales JSON de la variable de entorno.")
            
            # --- OPCIÓN 2: Usar archivo de credenciales (Local) ---
            elif os.getenv("FIREBASE_CREDENTIALS_PATH"):
                cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
                if os.path.exists(cred_path):
                    # Usar archivo local
                    cred = credentials.Certificate(cred_path)
                    logger.info("✅ Usando archivo local de credenciales.")
                else:
                    logger.warning(f"⚠️ Archivo de credenciales no encontrado en la ruta: {cred_path}")

            # --- Si no se encontraron credenciales válidas ---
            if not cred:
                logger.warning("⚠️ Firebase credentials not found. Database logging disabled.")
                return

            # Inicializar Firebase Admin
            # NOTA: Puede que necesites proporcionar el project_id si el certificado no lo tiene.
            firebase_admin.initialize_app(cred)
            
            # Obtener referencia a Firestore
            self.db = firestore.client()
            self.initialized = True
            
            logger.info("Firebase inicializado correctamente")
            
        except Exception as e:
            logger.error(f"Error al inicializar Firebase: {e}")
            self.db = None
    
    def save_single_analysis(self, comentario: str, resultado: Dict) -> Optional[str]:
        """
        Guarda un análisis individual en Firestore
        
        Args:
            comentario: El texto del comentario
            resultado: Resultado del análisis
            
        Returns:
            Document ID o None si falla
        """
        if not self.db:
            return None
        
        try:
            doc_data = {
                "tipo": "individual",
                "comentario": comentario,
                "etiqueta": resultado.get("etiqueta"),
                "confianza": resultado.get("confianza"),
                "porcentaje_positivo": resultado.get("porcentaje_positivo"),
                "porcentaje_negativo": resultado.get("porcentaje_negativo"),
                "timestamp": firestore.SERVER_TIMESTAMP,
                "fecha": datetime.now().isoformat()
            }
            
            # Guardar en colección 'analisis_individuales'
            doc_ref = self.db.collection("analisis_individuales").add(doc_data)
            
            logger.info(f"💾 Análisis individual guardado: {doc_ref[1].id}")
            return doc_ref[1].id
            
        except Exception as e:
            logger.error(f"❌ Error al guardar análisis individual: {e}")
            return None
    
    def save_batch_analysis(
        self, 
        filename: str, 
        total_comentarios: int,
        porcentaje_positivo: float,
        porcentaje_negativo: float,
        porcentaje_neutral: float,
        comentarios: List[Dict]
    ) -> Optional[str]:
        """
        Guarda un análisis batch (CSV/Excel) en Firestore
        
        Args:
            filename: Nombre del archivo procesado
            total_comentarios: Cantidad total de comentarios
            porcentaje_positivo: Porcentaje de comentarios positivos
            porcentaje_negativo: Porcentaje de comentarios negativos
            porcentaje_neutral: Porcentaje de comentarios neutrales
            comentarios: Lista de comentarios analizados
            
        Returns:
            Document ID o None si falla
        """
        if not self.db:
            return None
        
        try:
            # Crear documento del batch
            batch_data = {
                "tipo": "batch",
                "filename": filename,
                "total_comentarios": total_comentarios,
                "porcentaje_positivo_general": porcentaje_positivo,
                "porcentaje_negativo_general": porcentaje_negativo,
                "porcentaje_neutral": porcentaje_neutral,
                "timestamp": firestore.SERVER_TIMESTAMP,
                "fecha": datetime.now().isoformat()
            }
            
            # Guardar batch principal
            batch_ref = self.db.collection("analisis_batch").add(batch_data)
            batch_id = batch_ref[1].id
            
            # Guardar comentarios individuales dentro del batch
            # Usando subcollection para mejor organización
            comentarios_ref = self.db.collection("analisis_batch").document(batch_id).collection("comentarios")
            
            # Guardar en lotes de 500 (límite de Firestore batch write)
            batch_write = self.db.batch()
            count = 0
            
            for idx, comentario_data in enumerate(comentarios):
                doc_ref = comentarios_ref.document(f"comentario_{idx}")
                batch_write.set(doc_ref, {
                    "index": idx,
                    "comentario": comentario_data.get("comentario"),
                    "etiqueta": comentario_data.get("etiqueta"),
                    "confianza": comentario_data.get("confianza"),
                    "porcentaje_positivo": comentario_data.get("porcentaje_positivo"),
                    "porcentaje_negativo": comentario_data.get("porcentaje_negativo")
                })
                
                count += 1
                
                # Ejecutar batch cada 500 documentos
                if count >= 500:
                    batch_write.commit()
                    batch_write = self.db.batch()
                    count = 0
            
            # Commit final si quedan documentos
            if count > 0:
                batch_write.commit()
            
            logger.info(f"💾 Análisis batch guardado: {batch_id} ({total_comentarios} comentarios)")
            return batch_id
            
        except Exception as e:
            logger.error(f"Error al guardar análisis batch: {e}")
            return None
    
    def get_recent_analyses(self, limit: int = 10) -> List[Dict]:
        """
        Obtiene los análisis más recientes
        
        Args:
            limit: Cantidad máxima de documentos a retornar
            
        Returns:
            Lista de análisis
        """
        if not self.db:
            return []
        
        try:
            # Obtener análisis individuales
            individuales = (
                self.db.collection("analisis_individuales")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
            
            results = []
            for doc in individuales:
                data = doc.to_dict()
                data["id"] = doc.id
                results.append(data)
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error al obtener análisis recientes: {e}")
            return []
    
    def get_statistics(self) -> Dict:
        """
        Obtiene estadísticas generales de todos los análisis
        
        Returns:
            Diccionario con estadísticas
        """
        if not self.db:
            return {}
        
        try:
            # Contar análisis individuales
            individuales_count = len(list(
                self.db.collection("analisis_individuales").stream()
            ))
            
            # Contar análisis batch
            batch_count = len(list(
                self.db.collection("analisis_batch").stream()
            ))
            
            return {
                "total_analisis_individuales": individuales_count,
                "total_analisis_batch": batch_count,
                "total_general": individuales_count + batch_count
            }
            
        except Exception as e:
            logger.error(f"Error al obtener estadísticas: {e}")
            return {}

# Instancia global del servicio
firebase_service = FirebaseService()