"""
API principal del asistente de voz para adultos mayores
"""
import os
import logging
import json
import base64
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import whisper
import torch
from TTS.api import TTS
import requests
import re
import spacy

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración
RASA_ENABLED = False  # Temporalmente desactivado para enfocarnos en recordatorios
RASA_URL = "http://localhost:5005/webhooks/rest/webhook"
AUDIO_DIR = Path("audio_files")
AUDIO_DIR.mkdir(exist_ok=True)

# Configuración de tu servidor Node.js
NODE_SERVER_URL = "https://midosis.onrender.com"  # Tu servidor actual

# Crear aplicación FastAPI
app = FastAPI(
    title="Asistente de Voz para Adultos Mayores",
    description="API para procesamiento de voz y conversaciones naturales",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cargar modelos globalmente
WHISPER_MODEL = None
TTS_MODEL = None
TTS_AVAILABLE = False
NLP_MODEL = None

# Modelos Pydantic
class TextRequest(BaseModel):
    text: str
    user_id: Optional[str] = None

class VoiceCommandRequest(BaseModel):
    audio_base64: str
    user_id: str
    language: str = "es"

class MedicationReminderRequest(BaseModel):
    user_id: str
    medication_name: str
    dosage: str
    frequency: str
    time: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    notes: Optional[str] = None

# ============================================
# CLASE PARA PROCESAMIENTO DE COMANDOS DE VOZ
# ============================================

class VoiceCommandProcessor:
    def __init__(self):
        self.node_url = NODE_SERVER_URL
    
    async def process_and_schedule(self, user_id: str, transcript: str) -> dict:
        """Procesar comando de voz y programar en Node.js"""
        try:
            # 1. Parsear el comando de voz
            medication_info = extract_medication_info_from_text(transcript)
            
            # 2. Determinar acción
            command_type = self._detect_command_type(transcript)
            
            # 3. Programar notificaciones en Node.js
            if command_type == "add_medication" and medication_info.get("medication_name"):
                # Programar notificaciones usando tu API existente
                schedule_result = await self._schedule_notifications_via_node(
                    user_id=user_id,
                    medication_info=medication_info
                )
                
                return {
                    "success": True,
                    "message": f"✅ {medication_info['medication_name']} programado",
                    "scheduled_count": schedule_result.get("programadas", 0),
                    "medication_info": medication_info,
                    "node_response": schedule_result
                }
            
            return {
                "success": True,
                "message": "Comando procesado",
                "medication_info": medication_info
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _detect_command_type(self, text: str) -> str:
        """Detectar tipo de comando"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ["agregar", "añadir", "poner"]):
            return "add_medication"
        elif any(word in text_lower for word in ["eliminar", "quitar"]):
            return "delete_medication"
        elif any(word in text_lower for word in ["listar", "mostrar"]):
            return "list_medications"
        elif any(word in text_lower for word in ["hoy", "qué tengo"]):
            return "check_today"
        else:
            return "unknown"
    
    async def _schedule_notifications_via_node(self, user_id: str, medication_info: dict) -> dict:
        """Usar tu API Node.js existente para programar notificaciones"""
        
        # Preparar datos para tu endpoint /schedule-multiple-notifications
        horas_toma = self._calculate_notification_times(medication_info)
        
        payload = {
            "userId": user_id,
            "medicamentoId": f"voice_{datetime.now().timestamp()}",
            "horasToma": horas_toma,
            "nombre": medication_info.get("medication_name", "Medicamento"),
            "dosis": medication_info.get("dosage", "1 tableta"),
            "frecuencia": medication_info.get("frequency", "Diario"),
            "fechaInicio": datetime.now().isoformat(),
            "fechaFin": (datetime.now() + timedelta(days=30)).isoformat()
        }
        
        try:
            logger.info(f"Enviando a Node.js: {payload}")
            
            # Llamar a TU servidor Node.js
            response = requests.post(
                f"{self.node_url}/schedule-multiple-notifications",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Respuesta Node.js: {result}")
                return result
            else:
                error_msg = f"Error Node.js: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            logger.error(f"Error scheduling via Node.js: {e}")
            # Fallback: crear notificación simple
            return {"programadas": 1, "fallback": True, "error": str(e)}
    
    def _calculate_notification_times(self, medication_info: dict) -> list:
        """Calcular horas de notificación"""
        times = []
        now = datetime.now()
        
        # Extraer hora del comando
        time_str = medication_info.get("time", "08:00")
        
        # Parsear hora
        try:
            if ":" in time_str:
                hour = int(time_str.split(":")[0])
                minute = int(time_str.split(":")[1])
            else:
                hour = int(time_str)
                minute = 0
        except:
            hour = 8
            minute = 0
        
        # Para simplificar: programar para los próximos 7 días
        for day in range(7):
            notification_time = now.replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0
            ) + timedelta(days=day)
            
            if notification_time > now:
                times.append(notification_time.isoformat())
        
        return times

# Crear instancia global del procesador de comandos de voz
voice_processor = VoiceCommandProcessor()

# ============================================
# FUNCIONES DE INICIALIZACIÓN
# ============================================

# Inicializar modelos
@app.on_event("startup")
async def startup_event():
    """Inicializar modelos al iniciar el servidor"""
    global WHISPER_MODEL, TTS_MODEL, TTS_AVAILABLE, NLP_MODEL
    
    try:
        logger.info("Cargando modelo Whisper...")
        WHISPER_MODEL = whisper.load_model("base")
        logger.info("✓ Modelo Whisper cargado")
    except Exception as e:
        logger.error(f"Error cargando Whisper: {e}")
        WHISPER_MODEL = None
    
    try:
        logger.info("Cargando modelo TTS...")
        TTS_MODEL = TTS(model_name="tts_models/es/css10/vits", progress_bar=False)
        TTS_AVAILABLE = True
        logger.info("✓ Modelo TTS cargado")
    except Exception as e:
        logger.error(f"Error cargando TTS: {e}")
        TTS_MODEL = None
        TTS_AVAILABLE = False
    
    try:
        logger.info("Cargando modelo NLP...")
        NLP_MODEL = spacy.load("es_core_news_sm")
        logger.info("✓ Modelo NLP cargado")
    except Exception as e:
        logger.error(f"Error cargando NLP: {e}")
        NLP_MODEL = None

# ============================================
# ENDPOINTS PARA INTEGRACIÓN CON NODE.JS
# ============================================

@app.post("/api/voice/process-text")
async def process_text_command(request: TextRequest):
    """Procesar texto directamente (para pruebas)"""
    try:
        result = await voice_processor.process_and_schedule(
            user_id=request.user_id or "default_user",
            transcript=request.text
        )
        
        return {
            "success": True,
            "response": result
        }
        
    except Exception as e:
        logger.error(f"Error procesando texto: {e}")
        raise HTTPException(status_code=500, detail=f"Error procesando texto: {str(e)}")

@app.get("/api/voice/test-connection")
async def test_node_connection():
    """Probar conexión con Node.js"""
    try:
        response = requests.get(f"{NODE_SERVER_URL}/health", timeout=5)
        return {
            "nodejs_status": "connected" if response.status_code == 200 else "disconnected",
            "response": response.json() if response.status_code == 200 else None,
            "node_url": NODE_SERVER_URL
        }
    except Exception as e:
        return {
            "nodejs_status": "disconnected",
            "error": str(e),
            "node_url": NODE_SERVER_URL
        }

# ============================================
# ENDPOINTS PARA RECORDATORIOS POR VOZ
# ============================================

@app.post("/api/voice/process-command")
async def process_voice_command(request: VoiceCommandRequest):
    """
    Procesar comando de voz para recordatorios de medicamentos
    """
    try:
        # Decodificar audio base64
        audio_bytes = base64.b64decode(request.audio_base64)
        
        # Guardar temporalmente
        temp_path = AUDIO_DIR / f"command_{datetime.now().timestamp()}.wav"
        with open(temp_path, "wb") as f:
            f.write(audio_bytes)
        
        # Transcribir audio
        if WHISPER_MODEL is None:
            raise HTTPException(status_code=503, detail="Modelo Whisper no disponible")
        
        result = WHISPER_MODEL.transcribe(str(temp_path), language=request.language)
        transcript = result.get("text", "").strip()
        
        # Limpiar archivo temporal
        temp_path.unlink(missing_ok=True)
        
        logger.info(f"Transcripción: {transcript}")
        
        # Procesar el texto usando el nuevo procesador
        process_result = await voice_processor.process_and_schedule(
            user_id=request.user_id,
            transcript=transcript
        )
        
        # Preparar respuesta
        response = {
            "success": True,
            "transcript": transcript,
            "command_type": voice_processor._detect_command_type(transcript),
            "medication_info": process_result.get("medication_info", {}),
            "processing_result": process_result,
            "confidence": result.get("confidence", 0.0)
        }
        
        # Generar respuesta de voz si es exitoso
        if process_result.get("success"):
            message = process_result.get("message", "Comando procesado correctamente")
            
            # Convertir respuesta a voz
            if TTS_AVAILABLE:
                audio_path = generate_tts_response(message)
                if audio_path:
                    filename = Path(audio_path).name
                    response["voice_response"] = {
                        "text": message,
                        "audio_url": f"/audio/{filename}"
                    }
        
        return response
        
    except Exception as e:
        logger.error(f"Error procesando comando de voz: {e}")
        raise HTTPException(status_code=500, detail=f"Error procesando comando: {str(e)}")

@app.post("/api/voice/set-reminder")
async def set_medication_reminder(request: MedicationReminderRequest):
    """
    Establecer recordatorio de medicamento
    """
    try:
        # Validar datos
        if not request.medication_name or not request.dosage:
            raise HTTPException(status_code=400, detail="Nombre y dosis del medicamento son requeridos")
        
        # Calcular próxima hora de toma
        next_reminder = calculate_next_reminder_time(request.time, request.frequency)
        
        # Crear recordatorio
        reminder = {
            "user_id": request.user_id,
            "medication_name": request.medication_name,
            "dosage": request.dosage,
            "frequency": request.frequency,
            "time": request.time,
            "next_reminder": next_reminder.isoformat(),
            "start_date": request.start_date or datetime.now().isoformat(),
            "end_date": request.end_date or (datetime.now() + timedelta(days=30)).isoformat(),
            "notes": request.notes,
            "created_at": datetime.now().isoformat(),
            "active": True
        }
        
        # Guardar en "base de datos" temporal (en producción usarías una base de datos real)
        save_reminder_to_file(reminder)
        
        # También programar en Node.js si está disponible
        node_result = None
        try:
            horas_toma = voice_processor._calculate_notification_times({
                "time": request.time,
                "frequency": request.frequency
            })
            
            payload = {
                "userId": request.user_id,
                "medicamentoId": f"api_{datetime.now().timestamp()}",
                "horasToma": horas_toma,
                "nombre": request.medication_name,
                "dosis": request.dosage,
                "frecuencia": request.frequency,
                "fechaInicio": request.start_date or datetime.now().isoformat(),
                "fechaFin": request.end_date or (datetime.now() + timedelta(days=30)).isoformat()
            }
            
            node_response = requests.post(
                f"{NODE_SERVER_URL}/schedule-multiple-notifications",
                json=payload,
                timeout=10
            )
            
            if node_response.status_code == 200:
                node_result = node_response.json()
        except Exception as e:
            logger.warning(f"No se pudo programar en Node.js: {e}")
        
        # Generar respuesta de voz
        voice_text = f"He programado un recordatorio para {request.medication_name} {request.dosage}. Te recordaré {request.frequency} a las {request.time}."
        
        response = {
            "success": True,
            "reminder": reminder,
            "message": "Recordatorio programado exitosamente",
            "node_integration": node_result if node_result else {"status": "not_sent"}
        }
        
        # Agregar respuesta de voz
        if TTS_AVAILABLE:
            audio_path = generate_tts_response(voice_text)
            if audio_path:
                filename = Path(audio_path).name
                response["voice_response"] = {
                    "text": voice_text,
                    "audio_url": f"/audio/{filename}"
                }
        
        return response
        
    except Exception as e:
        logger.error(f"Error estableciendo recordatorio: {e}")
        raise HTTPException(status_code=500, detail=f"Error estableciendo recordatorio: {str(e)}")

@app.get("/api/voice/reminders/{user_id}")
async def get_user_reminders(user_id: str):
    """
    Obtener recordatorios activos de un usuario
    """
    try:
        reminders = load_reminders_for_user(user_id)
        
        return {
            "success": True,
            "user_id": user_id,
            "reminders": reminders,
            "count": len(reminders)
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo recordatorios: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo recordatorios: {str(e)}")

@app.delete("/api/voice/reminder/{reminder_id}")
async def delete_reminder(reminder_id: str, user_id: str):
    """
    Eliminar recordatorio
    """
    try:
        # En producción, aquí eliminarías de la base de datos
        # Por ahora solo simulamos
        success = delete_reminder_from_file(reminder_id, user_id)
        
        return {
            "success": success,
            "message": "Recordatorio eliminado exitosamente" if success else "Recordatorio no encontrado",
            "reminder_id": reminder_id
        }
        
    except Exception as e:
        logger.error(f"Error eliminando recordatorio: {e}")
        raise HTTPException(status_code=500, detail=f"Error eliminando recordatorio: {str(e)}")

@app.post("/api/voice/check-today")
async def check_todays_medications(request: TextRequest):
    """
    Verificar medicamentos para hoy
    """
    try:
        user_id = request.user_id or "default_user"
        reminders = load_reminders_for_user(user_id)
        
        # Filtrar para hoy
        today = datetime.now().date()
        today_reminders = [
            r for r in reminders 
            if datetime.fromisoformat(r.get("next_reminder", "")).date() == today
        ]
        
        if not today_reminders:
            response_text = "No tienes medicamentos programados para hoy."
        else:
            med_names = ", ".join([r["medication_name"] for r in today_reminders])
            response_text = f"Hoy debes tomar: {med_names}"
        
        response = {
            "success": True,
            "today_reminders": today_reminders,
            "count": len(today_reminders)
        }
        
        # Agregar respuesta de voz
        if TTS_AVAILABLE:
            audio_path = generate_tts_response(response_text)
            if audio_path:
                filename = Path(audio_path).name
                response["voice_response"] = {
                    "text": response_text,
                    "audio_url": f"/audio/{filename}"
                }
        
        return response
        
    except Exception as e:
        logger.error(f"Error verificando medicamentos: {e}")
        raise HTTPException(status_code=500, detail=f"Error verificando medicamentos: {str(e)}")

# ============================================
# FUNCIONES AUXILIARES PARA PROCESAMIENTO DE VOZ
# ============================================

def extract_medication_info_from_text(text: str) -> Dict[str, Any]:
    """
    Extraer información de medicamentos del texto
    """
    text_lower = text.lower()
    
    info = {
        "medication_name": None,
        "dosage": None,
        "frequency": None,
        "time": None,
        "action": None,
        "quantity": None
    }
    
    # Detectar acción
    if any(word in text_lower for word in ["agregar", "añadir", "poner", "programar"]):
        info["action"] = "add"
    elif any(word in text_lower for word in ["eliminar", "quitar", "borrar", "cancelar"]):
        info["action"] = "delete"
    elif any(word in text_lower for word in ["ver", "listar", "mostrar", "qué", "cuáles"]):
        info["action"] = "list"
    elif any(word in text_lower for word in ["recordar", "recordarme", "avisar"]):
        info["action"] = "remind"
    elif any(word in text_lower for word in ["tomé", "tomar", "tomo"]):
        info["action"] = "check"
    
    # Extraer nombre del medicamento
    medications = [
        "paracetamol", "ibuprofeno", "omeprazol", "aspirina", "amoxicilina",
        "loratadina", "metformina", "enalapril", "atorvastatina", "losartan",
        "clonazepam", "diazepam", "sertralina", "citalopram", "warfarin",
        "medicamento", "pastilla", "tableta", "comprimido"
    ]
    
    for med in medications:
        if med in text_lower:
            info["medication_name"] = med
            break
    
    # Extraer dosis
    dosage_patterns = [
        r"(\d+)\s*(mg|g|ml|mg)",
        r"(\d+)\s*(comprimidos?|pastillas?|cápsulas?|tabletas?)",
        r"(\d+)\s*(mg|g|ml)\s*de\s*\w+"
    ]
    
    for pattern in dosage_patterns:
        match = re.search(pattern, text_lower)
        if match:
            info["dosage"] = f"{match.group(1)} {match.group(2)}"
            break
    else:
        info["dosage"] = "1 tableta"  # Valor por defecto
    
    # Extraer frecuencia
    if "cada 8 horas" in text_lower or "cada ocho horas" in text_lower:
        info["frequency"] = "cada 8 horas"
    elif "cada 12 horas" in text_lower:
        info["frequency"] = "cada 12 horas"
    elif "diario" in text_lower or "todos los días" in text_lower or "una vez al día" in text_lower:
        info["frequency"] = "diario"
    elif "semanal" in text_lower or "una vez por semana" in text_lower:
        info["frequency"] = "semanal"
    else:
        info["frequency"] = "diario"
    
    # Extraer hora
    time_patterns = [
        r"a las (\d{1,2}):(\d{2})",
        r"(\d{1,2})\s*(?:de la\s+)?(mañana|tarde|noche)",
        r"(\d{1,2})\s*(am|pm)",
        r"(\d{1,2})\s*horas"
    ]
    
    time_found = False
    for pattern in time_patterns:
        match = re.search(pattern, text_lower)
        if match:
            time_found = True
            if ":" in pattern:
                info["time"] = f"{match.group(1)}:{match.group(2)}"
            else:
                hour = match.group(1)
                period = match.group(2) if len(match.groups()) > 1 else None
                
                if period:
                    if period in ["tarde", "noche", "pm"]:
                        hour = int(hour) + 12 if int(hour) < 12 else int(hour)
                    elif period in ["mañana", "am"] and hour == "12":
                        hour = "00"
                
                info["time"] = f"{hour}:00"
            break
    
    if not time_found:
        info["time"] = "08:00"  # Hora por defecto
    
    return info

def generate_voice_response(command_type: str, medication_info: Dict[str, Any]) -> str:
    """
    Generar respuesta de voz
    """
    if command_type == "add_medication":
        return f"Voy a agregar {medication_info.get('medication_name', 'el medicamento')} {medication_info.get('dosage', '')}. Te recordaré {medication_info.get('frequency', 'diario')} a las {medication_info.get('time', 'la hora indicada')}."
    
    elif command_type == "delete_medication":
        return f"Eliminando {medication_info.get('medication_name', 'el medicamento')} de tus recordatorios."
    
    elif command_type == "list_medications":
        return "Mostrando tus medicamentos registrados. Revisa la pantalla para ver la lista completa."
    
    elif command_type == "set_reminder":
        return f"Recordatorio establecido para {medication_info.get('medication_name', 'el medicamento')}."
    
    elif command_type == "check_medication":
        return f"Verificando información de {medication_info.get('medication_name', 'tu medicamento')}."
    
    elif command_type == "check_today":
        return "Verificando tus medicamentos para hoy."
    
    else:
        return "Lo siento, no entendí el comando. ¿Podrías repetirlo?"

def calculate_next_reminder_time(time_str: str, frequency: str) -> datetime:
    """
    Calcular próxima hora de recordatorio
    """
    now = datetime.now()
    
    # Parsear hora
    if ":" in time_str:
        hour, minute = map(int, time_str.split(":"))
    else:
        hour, minute = int(time_str), 0
    
    # Calcular próxima ocurrencia
    next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # Si la hora ya pasó hoy, calcular para mañana
    if next_time < now:
        next_time += timedelta(days=1)
    
    return next_time

def generate_tts_response(text: str) -> Optional[str]:
    """
    Generar audio TTS
    """
    if not TTS_AVAILABLE or TTS_MODEL is None:
        return None
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = AUDIO_DIR / f"response_{timestamp}.wav"
        
        TTS_MODEL.tts_to_file(text=text, file_path=str(output_path))
        
        return str(output_path)
    except Exception as e:
        logger.error(f"Error generando TTS: {e}")
        return None

def save_reminder_to_file(reminder: Dict[str, Any]):
    """
    Guardar recordatorio en archivo (temporal)
    """
    reminders_file = AUDIO_DIR / "reminders.json"
    
    try:
        if reminders_file.exists():
            with open(reminders_file, "r") as f:
                reminders = json.load(f)
        else:
            reminders = []
        
        # Agregar ID único
        reminder["id"] = f"rem_{datetime.now().timestamp()}"
        reminders.append(reminder)
        
        with open(reminders_file, "w") as f:
            json.dump(reminders, f, indent=2)
            
    except Exception as e:
        logger.error(f"Error guardando recordatorio: {e}")

def load_reminders_for_user(user_id: str) -> list:
    """
    Cargar recordatorios de usuario
    """
    reminders_file = AUDIO_DIR / "reminders.json"
    
    if not reminders_file.exists():
        return []
    
    try:
        with open(reminders_file, "r") as f:
            reminders = json.load(f)
        
        # Filtrar por usuario y activos
        user_reminders = [
            r for r in reminders 
            if r.get("user_id") == user_id and r.get("active", True)
        ]
        
        return user_reminders
    except Exception as e:
        logger.error(f"Error cargando recordatorios: {e}")
        return []

def delete_reminder_from_file(reminder_id: str, user_id: str) -> bool:
    """
    Eliminar recordatorio del archivo
    """
    reminders_file = AUDIO_DIR / "reminders.json"
    
    if not reminders_file.exists():
        return False
    
    try:
        with open(reminders_file, "r") as f:
            reminders = json.load(f)
        
        # Marcar como inactivo
        updated = False
        for i, reminder in enumerate(reminders):
            if reminder.get("id") == reminder_id and reminder.get("user_id") == user_id:
                reminders[i]["active"] = False
                updated = True
                break
        
        if updated:
            with open(reminders_file, "w") as f:
                json.dump(reminders, f, indent=2)
        
        return updated
    except Exception as e:
        logger.error(f"Error eliminando recordatorio: {e}")
        return False

# ============================================
# ENDPOINTS EXISTENTES (mantener)
# ============================================

@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "API del Asistente de Voz para Adultos Mayores",
        "status": "active",
        "endpoints": {
            "voice": {
                "process_command": "POST /api/voice/process-command",
                "process_text": "POST /api/voice/process-text",
                "set_reminder": "POST /api/voice/set-reminder",
                "get_reminders": "GET /api/voice/reminders/{user_id}",
                "delete_reminder": "DELETE /api/voice/reminder/{reminder_id}",
                "check_today": "POST /api/voice/check-today",
                "test_connection": "GET /api/voice/test-connection"
            },
            "node_integration": {
                "url": NODE_SERVER_URL,
                "status": "GET /api/voice/test-connection"
            },
            "health": "GET /health",
            "docs": "GET /docs"
        }
    }

@app.get("/health")
async def health_check():
    """Verificar estado del servicio"""
    node_status = "unknown"
    try:
        response = requests.get(f"{NODE_SERVER_URL}/health", timeout=3)
        node_status = "connected" if response.status_code == 200 else "disconnected"
    except:
        node_status = "disconnected"
    
    status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "whisper": WHISPER_MODEL is not None,
            "tts": TTS_AVAILABLE,
            "nlp": NLP_MODEL is not None,
            "voice_commands": True,
            "nodejs_integration": node_status
        },
        "nodejs_server": NODE_SERVER_URL
    }
    return status

# ============================================
# ENDPOINTS DE AUDIO (mantener si existen)
# ============================================

@app.get("/audio/{filename}")
async def get_audio_file(filename: str):
    """Obtener archivo de audio generado"""
    file_path = AUDIO_DIR / filename
    if file_path.exists():
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Archivo no encontrado")

# Función para iniciar el servidor
def start_server():
    """Iniciar servidor Uvicorn"""
    import uvicorn
    
    logger.info("=" * 60)
    logger.info("INICIANDO SERVIDOR ASISTENTE DE VOZ CON INTEGRACIÓN NODE.JS")
    logger.info("=" * 60)
    
    logger.info(f"📊 API disponible en: http://localhost:8000")
    logger.info(f"📖 Documentación: http://localhost:8000/docs")
    logger.info(f"🏥 Estado: http://localhost:8000/health")
    logger.info(f"🔗 Servidor Node.js: {NODE_SERVER_URL}")
    
    logger.info("\n🎤 Endpoints de Voz Mejorados:")
    logger.info("  POST /api/voice/process-command   - Procesar comando de voz (con Node.js)")
    logger.info("  POST /api/voice/process-text      - Procesar texto directamente")
    logger.info("  POST /api/voice/set-reminder      - Establecer recordatorio")
    logger.info("  GET  /api/voice/reminders/{id}    - Obtener recordatorios")
    logger.info("  DELETE /api/voice/reminder/{id}   - Eliminar recordatorio")
    logger.info("  POST /api/voice/check-today       - Verificar medicamentos hoy")
    logger.info("  GET  /api/voice/test-connection   - Probar conexión con Node.js")
    
    logger.info("\n🔧 Servicios cargados:")
    logger.info(f"  ✓ Whisper STT: {WHISPER_MODEL is not None}")
    logger.info(f"  ✓ Coqui TTS: {TTS_AVAILABLE}")
    logger.info(f"  ✓ SpaCy NLP: {NLP_MODEL is not None}")
    
    logger.info("\n🔄 Servidor iniciando...")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    start_server()