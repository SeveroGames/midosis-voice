"""
Servicio TTS con Coqui y fallback a pyttsx3
"""
import os
import sys
from pathlib import Path
import logging
from typing import Optional, Tuple
import tempfile
import threading

logger = logging.getLogger(__name__)

# Intentar importar Coqui TTS
COQUI_AVAILABLE = False
PYTTSX3_AVAILABLE = False

try:
    from TTS.api import TTS
    import torch
    COQUI_AVAILABLE = True
    logger.info("Coqui TTS disponible")
except ImportError as e:
    logger.warning(f"Coqui TTS no disponible: {e}")

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
    logger.info("pyttsx3 disponible como fallback")
except ImportError as e:
    logger.warning(f"pyttsx3 no disponible: {e}")

class BaseTTS:
    """Clase base para servicios TTS"""
    def __init__(self):
        self.output_dir = Path(__file__).parent.parent / "audio"
        self.output_dir.mkdir(exist_ok=True)
    
    def synthesize(self, text: str, output_path: Optional[str] = None) -> Optional[str]:
        raise NotImplementedError
    
    def _sanitize_text(self, text: str) -> str:
        """Limpiar texto para TTS"""
        # Reemplazar caracteres problemáticos
        replacements = {
            '&': 'y',
            '%': 'por ciento',
            '$': 'dólares',
            '#': 'número',
            '@': 'arroba'
        }
        
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        
        return text.strip()

class CoquiTTS(BaseTTS):
    """Implementación con Coqui TTS"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CoquiTTS, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        super().__init__()
        
        if not COQUI_AVAILABLE:
            raise RuntimeError("Coqui TTS no está disponible")
        
        try:
            # Listar modelos disponibles
            available_models = TTS().list_models()
            logger.info(f"Modelos TTS disponibles: {available_models}")
            
            # Seleccionar modelo en español
            spanish_models = [
                "tts_models/es/css10/vits",
                "tts_models/es/mai/tacotron2-DDC",
                "tts_models/es/mai/fast_pitch"
            ]
            
            self.model_name = None
            for model in spanish_models:
                if model in available_models:
                    self.model_name = model
                    break
            
            if not self.model_name:
                logger.warning("No se encontró modelo español, usando inglés")
                self.model_name = "tts_models/en/ljspeech/tacotron2-DDC"
            
            # Inicializar TTS
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Inicializando TTS modelo {self.model_name} en {self.device}")
            
            self.tts = TTS(self.model_name, gpu=(self.device == "cuda"))
            
            logger.info("✓ Coqui TTS inicializado exitosamente")
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Error inicializando Coqui TTS: {e}")
            raise
    
    def synthesize(self, text: str, output_path: Optional[str] = None) -> Optional[str]:
        """Convertir texto a voz con Coqui"""
        if not self._initialized:
            raise RuntimeError("Coqui TTS no inicializado")
        
        if not text or len(text.strip()) == 0:
            logger.warning("Texto vacío para TTS")
            return None
        
        try:
            # Limpiar texto
            text = self._sanitize_text(text)
            
            # Definir ruta de salida
            if output_path is None:
                output_path = self.output_dir / "output.wav"
            else:
                output_path = Path(output_path)
            
            # Crear directorio si no existe
            output_path.parent.mkdir(exist_ok=True, parents=True)
            
            logger.info(f"Generando audio para texto de {len(text)} caracteres")
            
            # Generar audio
            self.tts.tts_to_file(
                text=text,
                file_path=str(output_path),
                speaker=self.tts.speakers[0] if hasattr(self.tts, 'speakers') and self.tts.speakers else None,
                language=self.tts.languages[0] if hasattr(self.tts, 'languages') and self.tts.languages else None
            )
            
            if output_path.exists():
                logger.info(f"Audio generado: {output_path}")
                return str(output_path)
            else:
                logger.error("Audio no generado")
                return None
                
        except Exception as e:
            logger.error(f"Error en síntesis Coqui: {e}")
            return None

class PyTTSX3TTS(BaseTTS):
    """Implementación fallback con pyttsx3"""
    
    def __init__(self):
        super().__init__()
        
        if not PYTTSX3_AVAILABLE:
            raise RuntimeError("pyttsx3 no está disponible")
        
        try:
            self.engine = pyttsx3.init()
            
            # Configurar propiedades
            self.engine.setProperty('rate', 150)  # Velocidad
            self.engine.setProperty('volume', 0.9)  # Volumen
            
            # Buscar voz en español
            voices = self.engine.getProperty('voices')
            spanish_voice = None
            
            for voice in voices:
                if 'spanish' in voice.name.lower() or 'español' in voice.name.lower():
                    spanish_voice = voice.id
                    break
            
            if spanish_voice:
                self.engine.setProperty('voice', spanish_voice)
            
            logger.info("✓ pyttsx3 inicializado")
            
        except Exception as e:
            logger.error(f"Error inicializando pyttsx3: {e}")
            raise
    
    def synthesize(self, text: str, output_path: Optional[str] = None) -> Optional[str]:
        """Convertir texto a voz con pyttsx3"""
        if not text or len(text.strip()) == 0:
            return None
        
        try:
            text = self._sanitize_text(text)
            
            if output_path is None:
                output_path = self.output_dir / "output_fallback.wav"
            else:
                output_path = Path(output_path)
            
            output_path.parent.mkdir(exist_ok=True, parents=True)
            
            # pyttsx3 necesita guardar a archivo
            self.engine.save_to_file(text, str(output_path))
            self.engine.runAndWait()
            
            if output_path.exists():
                logger.info(f"Audio generado (fallback): {output_path}")
                return str(output_path)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error en síntesis pyttsx3: {e}")
            return None

# Gestor de TTS principal
class TTSService:
    """Gestor que usa Coqui con fallback a pyttsx3"""
    
    def __init__(self):
        self.coqui = None
        self.pyttsx3 = None
        
        # Intentar Coqui primero
        if COQUI_AVAILABLE:
            try:
                self.coqui = CoquiTTS()
                logger.info("Usando Coqui TTS como motor principal")
            except Exception as e:
                logger.warning(f"No se pudo inicializar Coqui: {e}")
        
        # Fallback a pyttsx3
        if self.coqui is None and PYTTSX3_AVAILABLE:
            try:
                self.pyttsx3 = PyTTSX3TTS()
                logger.info("Usando pyttsx3 como motor de respaldo")
            except Exception as e:
                logger.warning(f"No se pudo inicializar pyttsx3: {e}")
        
        if self.coqui is None and self.pyttsx3 is None:
            logger.error("Ningún motor TTS disponible")
    
    def synthesize(self, text: str, output_path: Optional[str] = None) -> Optional[str]:
        """Convertir texto a voz usando el mejor motor disponible"""
        if not text:
            return None
        
        # Intentar Coqui primero
        if self.coqui:
            result = self.coqui.synthesize(text, output_path)
            if result:
                return result
        
        # Fallback a pyttsx3
        if self.pyttsx3:
            result = self.pyttsx3.synthesize(text, output_path)
            if result:
                logger.info("Usando TTS de respaldo (pyttsx3)")
                return result
        
        logger.error("No se pudo generar audio")
        return None
    
    def get_status(self) -> dict:
        """Obtener estado del servicio TTS"""
        return {
            "coqui_available": self.coqui is not None,
            "pyttsx3_available": self.pyttsx3 is not None,
            "engine": "coqui" if self.coqui else ("pyttsx3" if self.pyttsx3 else "none")
        }

# Instancia global
_tts_service = None

def get_tts_service() -> TTSService:
    """Obtener instancia del servicio TTS"""
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service

def text_to_speech(text: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Función simplificada para síntesis de voz
    
    Args:
        text: Texto a convertir
        output_path: Ruta opcional para guardar audio
    
    Returns:
        Ruta al archivo de audio o None si falla
    """
    try:
        service = get_tts_service()
        return service.synthesize(text, output_path)
    except Exception as e:
        logger.error(f"Error en text_to_speech: {e}")
        return None

# Prueba rápida
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    service = get_tts_service()
    print(f"Estado TTS: {service.get_status()}")
    
    # Probar síntesis
    test_text = "Hola, este es un prueba del sistema de voz."
    result = text_to_speech(test_text)
    
    if result:
        print(f"Audio generado: {result}")
    else:
        print("Error generando audio")