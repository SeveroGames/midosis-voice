"""
Servicio Whisper STT optimizado - Servidor FastAPI con funcionalidades avanzadas
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import whisper
import torch
import numpy as np
import soundfile as sf
import base64
import tempfile
import os
import io
import re
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
import asyncio
import aiofiles
from dataclasses import dataclass, asdict
import uuid

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class TranscriptionResult:
    """Estructura de datos para resultados de transcripción"""
    success: bool
    text: str = ""
    original_text: str = ""
    language: str = "es"
    confidence: float = 0.0
    processing_time: float = 0.0
    audio_quality: Optional[Dict[str, Any]] = None
    has_speech: bool = False
    is_command: Optional[bool] = None
    error: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: str = ""

class WhisperSTTService:
    """Servicio Whisper con pooling de modelos y caché"""
    
    _instance = None
    _models_pool = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WhisperSTTService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, 
                 default_model: str = "base",
                 max_models_in_memory: int = 2,
                 device: Optional[str] = None):
        if self._initialized:
            return
            
        self.default_model = default_model
        self.max_models = max_models_in_memory
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model_dir = Path(__file__).parent / "models"
        self.model_dir.mkdir(exist_ok=True)
        
        logger.info(f"Inicializando WhisperService en {self.device}")
        logger.info(f"Modelo por defecto: {default_model}")
        
        # Cargar modelo por defecto
        self.current_model = self.load_model(default_model)
        self._initialized = True
        
    def load_model(self, model_size: str = "base") -> whisper.Whisper:
        """Cargar modelo Whisper con caché"""
        if model_size in self._models_pool:
            logger.info(f"Modelo {model_size} ya cargado en memoria")
            return self._models_pool[model_size]
        
        # Si excedemos el límite, eliminar el menos usado
        if len(self._models_pool) >= self.max_models:
            oldest_model = list(self._models_pool.keys())[0]
            del self._models_pool[oldest_model]
            logger.info(f"Liberado modelo {oldest_model} de la memoria")
        
        try:
            logger.info(f"Cargando modelo {model_size}...")
            model = whisper.load_model(
                model_size,
                device=self.device,
                download_root=self.model_dir
            )
            self._models_pool[model_size] = model
            logger.info(f"✓ Modelo {model_size} cargado exitosamente")
            return model
            
        except Exception as e:
            logger.error(f"Error cargando modelo {model_size}: {e}")
            raise
    
    def get_transcription_config(self, 
                                language: str = "es",
                                task: str = "transcribe") -> Dict[str, Any]:
        """Configuración optimizada para transcripción"""
        return {
            "task": task,
            "language": language if language != "auto" else None,
            "fp16": torch.cuda.is_available(),
            "verbose": False,
            "temperature": 0.0,
            "best_of": 1,
            "beam_size": 1,
            "patience": 1.0,
            "length_penalty": -0.5,
            "suppress_tokens": [-1],
            "initial_prompt": "Esto es un comando de voz para medicamentos.",
            "condition_on_previous_text": False,
            "compression_ratio_threshold": 2.4,
            "logprob_threshold": -1.0,
            "no_speech_threshold": 0.6
        }
    
    async def transcribe_base64(self, 
                               audio_base64: str,
                               language: str = "es",
                               request_id: Optional[str] = None) -> TranscriptionResult:
        """Transcribir audio en formato base64 (versión asíncrona)"""
        request_id = request_id or str(uuid.uuid4())[:8]
        start_time = datetime.now()
        
        try:
            # Decodificar base64
            logger.info(f"[{request_id}] Decodificando audio base64...")
            audio_bytes = base64.b64decode(audio_base64)
            
            # Crear archivo temporal
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp.write(audio_bytes)
                    temp_path = tmp.name
                
                # Transcribir
                logger.info(f"[{request_id}] Transcribiendo audio...")
                config = self.get_transcription_config(language)
                result = await asyncio.to_thread(
                    self.current_model.transcribe,
                    temp_path,
                    **config
                )
                
                # Procesar resultados
                text = result.get("text", "").strip()
                language_detected = result.get("language", language)
                
                # Analizar calidad de audio
                audio_quality = await self.analyze_audio_quality(temp_path)
                
                # Calcular confianza
                confidence = self.calculate_confidence(result, audio_quality)
                
                # Limpiar texto
                cleaned_text = self.clean_transcription(text)
                
                # Determinar si es comando
                is_command = self.is_command_like(cleaned_text) if cleaned_text else False
                
                processing_time = (datetime.now() - start_time).total_seconds()
                
                logger.info(f"[{request_id}] Transcripción completada en {processing_time:.2f}s")
                logger.info(f"[{request_id}] Texto: {cleaned_text[:100]}...")
                
                return TranscriptionResult(
                    success=True,
                    text=cleaned_text,
                    original_text=text,
                    language=language_detected,
                    confidence=confidence,
                    processing_time=processing_time,
                    audio_quality=audio_quality,
                    has_speech=len(text) > 0,
                    is_command=is_command,
                    request_id=request_id,
                    timestamp=datetime.now().isoformat()
                )
                
            finally:
                # Limpiar archivo temporal
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except Exception as e:
            logger.error(f"[{request_id}] Error en transcripción: {e}")
            return TranscriptionResult(
                success=False,
                error=str(e),
                request_id=request_id,
                timestamp=datetime.now().isoformat()
            )
    
    async def analyze_audio_quality(self, audio_path: str) -> Dict[str, Any]:
        """Analizar calidad del audio de forma asíncrona"""
        try:
            audio, sample_rate = sf.read(audio_path)
            
            # Calcular métricas básicas
            duration = len(audio) / sample_rate
            max_amplitude = np.max(np.abs(audio))
            rms = np.sqrt(np.mean(audio**2))
            
            # Calcular SNR aproximado
            noise_floor = np.percentile(np.abs(audio), 10)
            snr = 20 * np.log10(rms / (noise_floor + 1e-10)) if noise_floor > 0 else 0
            
            return {
                "duration": float(duration),
                "sample_rate": sample_rate,
                "max_amplitude": float(max_amplitude),
                "rms": float(rms),
                "snr": float(snr),
                "channels": 1 if len(audio.shape) == 1 else audio.shape[1],
                "has_audio": duration > 0.1 and max_amplitude > 0.01,
                "samples": len(audio)
            }
            
        except Exception as e:
            logger.warning(f"Error analizando calidad de audio: {e}")
            return {
                "duration": 0,
                "has_audio": False,
                "error": str(e)
            }
    
    def calculate_confidence(self, 
                            result: Dict[str, Any], 
                            audio_quality: Dict[str, Any]) -> float:
        """Calcular confianza de la transcripción"""
        confidence = 1.0
        
        # Basado en probabilidades de Whisper
        if "segments" in result and result["segments"]:
            avg_prob = np.mean([seg.get("avg_logprob", -10) for seg in result["segments"]])
            confidence *= max(0.1, 1 + avg_prob / 10)
        
        # Basado en calidad de audio
        if audio_quality.get("has_audio", False):
            snr = audio_quality.get("snr", 0)
            if snr > 20:
                confidence *= 1.2
            elif snr < 5:
                confidence *= 0.7
        
        # Basado en duración
        duration = audio_quality.get("duration", 0)
        if duration < 0.5:
            confidence *= 0.5
        elif duration > 10:
            confidence *= 0.8
        
        return min(1.0, max(0.0, confidence))
    
    def clean_transcription(self, text: str) -> str:
        """Limpiar y normalizar texto transcrito"""
        if not text:
            return ""
        
        # Remover espacios extras
        text = ' '.join(text.split())
        
        # Capitalizar primera letra
        if text:
            text = text[0].upper() + text[1:]
        
        # Remover puntuación extra al final
        text = text.rstrip('.!?')
        
        # Añadir punto final si no hay
        if text and not text.endswith(('.', '!', '?')):
            text += '.'
        
        return text
    
    def is_command_like(self, text: str) -> bool:
        """Determinar si el texto parece un comando"""
        if not text:
            return False
        
        text_lower = text.lower()
        
        # Patrones de comandos comunes para medicamentos
        command_patterns = [
            r"agregar|añadir|poner",
            r"eliminar|quitar|borrar",
            r"listar|mostrar|ver",
            r"recordar|recordarme|avisar",
            r"tomar|tomo|tomé|medicar",
            r"medicamento|pastilla|tableta|cápsula|jarabe",
            r"(\d+)\s*(mg|g|ml|cc)",
            r"a las \d{1,2}",
            r"cada \d+\s*(hora|horas|día|días)",
            r"antes|después|con",
            r"comida|desayuno|almuerzo|cena",
            r"paracetamol|ibuprofeno|aspirina|omeprazol"
        ]
        
        for pattern in command_patterns:
            if re.search(pattern, text_lower):
                return True
        
        return False
    
    def get_service_info(self) -> Dict[str, Any]:
        """Obtener información del servicio"""
        return {
            "status": "running",
            "default_model": self.default_model,
            "device": self.device,
            "models_loaded": list(self._models_pool.keys()),
            "max_models_in_memory": self.max_models,
            "supported_languages": ["es", "en", "fr", "de", "it", "pt", "ja", "zh", "auto"],
            "initialized": self._initialized,
            "timestamp": datetime.now().isoformat()
        }

# Lifespan management para FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Administrar el ciclo de vida de la aplicación"""
    # Startup
    logger.info("Iniciando Whisper Service...")
    app.state.whisper_service = WhisperSTTService()
    logger.info("✓ Whisper Service listo")
    
    yield
    
    # Shutdown
    logger.info("Apagando Whisper Service...")
    # Limpiar recursos si es necesario

# Crear aplicación FastAPI
app = FastAPI(
    title="Whisper STT Service",
    description="Servicio de transcripción de voz a texto usando Whisper",
    version="2.0.0",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoints
@app.get("/")
async def root():
    """Endpoint de salud"""
    return {
        "service": "Whisper STT",
        "status": "online",
        "version": "2.0.0",
        "documentation": "/docs"
    }

@app.get("/health")
async def health_check():
    """Verificar salud del servicio"""
    service = app.state.whisper_service
    return {
        "status": "healthy",
        "service_info": service.get_service_info(),
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/transcribe")
async def transcribe_audio(data: dict, background_tasks: BackgroundTasks):
    """
    Transcribir audio en formato base64
    
    Body:
    {
        "audio_base64": "base64_string",
        "language": "es",
        "task": "transcribe"
    }
    """
    try:
        # Validar entrada
        audio_b64 = data.get("audio_base64")
        if not audio_b64:
            raise HTTPException(status_code=400, detail="No audio data provided")
        
        language = data.get("language", "es")
        task = data.get("task", "transcribe")
        
        # Generar ID de solicitud para tracking
        request_id = str(uuid.uuid4())[:8]
        
        logger.info(f"[{request_id}] Nueva solicitud de transcripción - Idioma: {language}")
        
        # Procesar transcripción
        service = app.state.whisper_service
        result = await service.transcribe_base64(audio_b64, language, request_id)
        
        # Convertir a dict para respuesta
        response_data = asdict(result)
        
        # Remover campos None para respuesta limpia
        response_data = {k: v for k, v in response_data.items() if v is not None}
        
        return JSONResponse(content=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint /api/transcribe: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/api/transcribe/batch")
async def transcribe_batch(data: dict):
    """
    Transcribir múltiples audios en lote
    
    Body:
    {
        "audios": [
            {"audio_base64": "base64_1", "language": "es"},
            {"audio_base64": "base64_2", "language": "en"}
        ]
    }
    """
    try:
        audios = data.get("audios", [])
        if not audios:
            raise HTTPException(status_code=400, detail="No audios provided")
        
        if len(audios) > 10:  # Límite de lote
            raise HTTPException(status_code=400, detail="Maximum 10 audios per batch")
        
        logger.info(f"Procesando lote de {len(audios)} audios")
        
        # Procesar en paralelo
        service = app.state.whisper_service
        tasks = [
            service.transcribe_base64(
                audio.get("audio_base64", ""),
                audio.get("language", "es"),
                f"batch_{i}"
            )
            for i, audio in enumerate(audios)
        ]
        
        results = await asyncio.gather(*tasks)
        
        return {
            "success": True,
            "batch_id": str(uuid.uuid4())[:8],
            "count": len(results),
            "results": [asdict(r) for r in results],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error en transcripción por lote: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/models/available")
async def get_available_models():
    """Obtener modelos disponibles"""
    return {
        "models": ["tiny", "base", "small", "medium", "large"],
        "recommended": "base",
        "description": "Para comandos de voz, 'base' es suficiente"
    }

@app.post("/api/models/switch")
async def switch_model(data: dict):
    """Cambiar el modelo activo"""
    try:
        model_size = data.get("model", "base")
        if model_size not in ["tiny", "base", "small", "medium", "large"]:
            raise HTTPException(status_code=400, detail="Modelo no válido")
        
        service = app.state.whisper_service
        service.current_model = service.load_model(model_size)
        service.default_model = model_size
        
        logger.info(f"Modelo cambiado a: {model_size}")
        
        return {
            "success": True,
            "message": f"Model switched to {model_size}",
            "model_info": service.get_service_info()
        }
        
    except Exception as e:
        logger.error(f"Error cambiando modelo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze/command")
async def analyze_command(data: dict):
    """Analizar si un texto parece un comando"""
    text = data.get("text", "")
    
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")
    
    service = app.state.whisper_service
    is_command = service.is_command_like(text)
    
    # Análisis detallado
    patterns = [
        ("Medicamento", r"medicamento|pastilla|tableta|cápsula|jarabe"),
        ("Dosis", r"(\d+)\s*(mg|g|ml|cc)"),
        ("Horario", r"a las \d{1,2}|cada \d+\s*(hora|horas|día|días)"),
        ("Acción", r"agregar|eliminar|recordar|tomar"),
        ("Relación comida", r"antes|después|con\s+(comida|desayuno|almuerzo|cena)")
    ]
    
    matches = []
    for name, pattern in patterns:
        if re.search(pattern, text.lower()):
            matches.append(name)
    
    return {
        "text": text,
        "is_command": is_command,
        "confidence": len(matches) / len(patterns) if patterns else 0,
        "matched_patterns": matches,
        "analysis": "Es un comando de medicamentos" if is_command else "No parece un comando específico"
    }

# Middleware para logging de requests
@app.middleware("http")
async def log_requests(request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start_time = datetime.now()
    
    logger.info(f"[{request_id}] {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    process_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"[{request_id}] Completed in {process_time:.3f}s - Status: {response.status_code}")
    
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(process_time)
    
    return response

if __name__ == "__main__":
    import uvicorn
    
    # Configuración del servidor
    host = os.getenv("WHISPER_HOST", "0.0.0.0")
    port = int(os.getenv("WHISPER_PORT", "8001"))
    
    logger.info(f"Iniciando servidor Whisper en {host}:{port}")
    logger.info("Documentación disponible en /docs")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )