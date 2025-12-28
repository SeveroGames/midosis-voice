"""
Servidor FastAPI con soporte para comandos 'Mi Dosis'
"""
import os
import sys
import logging
import json
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ========== CONFIGURAR PATH PARA IMPORTACIONES ==========
# Añadir el directorio padre al sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # Sube un nivel (a la raíz)
sys.path.insert(0, parent_dir)  # Añadir raíz al path

logger = logging.getLogger(__name__)

# ========== IMPORTAR PARSER ==========
def import_parser():
    """Importar el parser de medicamentos"""
    try:
        # Verificar si existe el módulo nlp
        import importlib.util
        nlp_path = os.path.join(parent_dir, "nlp", "medication_parser.py")
        
        if os.path.exists(nlp_path):
            logger.info(f"✅ Encontrado parser en: {nlp_path}")
            
            # Importar usando importlib
            spec = importlib.util.spec_from_file_location(
                "medication_parser", 
                nlp_path
            )
            parser_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(parser_module)
            
            # Obtener funciones
            extract_func = getattr(parser_module, "extract_medication_info")
            format_func = getattr(parser_module, "format_medication_response")
            
            logger.info("✅ Parser importado exitosamente")
            return extract_func, format_func
        else:
            logger.warning(f"⚠️ Archivo no encontrado: {nlp_path}")
            raise FileNotFoundError(f"No se encontró {nlp_path}")
            
    except Exception as e:
        logger.error(f"❌ Error importando parser: {e}")
        
        # Crear funciones dummy como fallback
        def dummy_extract(text):
            return {
                "text": text,
                "medication": "medicamento_prueba",
                "dosage": "500mg",
                "frequency": "diario",
                "action": "add_medication",
                "is_dosis_command": "mi dosis" in text.lower(),
                "confidence": 0.7
            }
        
        def dummy_format(parsed):
            return f"Medicamento: {parsed.get('medication', 'desconocido')}"
        
        logger.info("⚠️ Usando parser dummy")
        return dummy_extract, dummy_format

# Importar funciones
extract_medication_info, format_medication_response = import_parser()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# Configuración
NODE_SERVER_URL = "https://midosis.onrender.com"

# Crear aplicación FastAPI
app = FastAPI(
    title="Asistente de Voz para Medicamentos con Mi Dosis",
    description="API para procesar comandos de voz para medicamentos con soporte para 'Mi Dosis'",
    version="2.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos Pydantic
class VoiceCommandRequest(BaseModel):
    text: str
    user_id: str

class DosisCommandRequest(BaseModel):
    userId: str
    transcript: str
    commandType: str
    medicationInfo: Dict[str, Any]
    components: Optional[Dict[str, Any]] = None
    is_dosis_command: bool = False

class MedicationRequest(BaseModel):
    user_id: str
    nombre: str
    dosis: str
    frecuencia: str
    hora: str
    fecha_inicio: str
    fecha_fin: str

@app.get("/")
async def root():
    return {
        "message": "Asistente de Voz para Medicamentos con 'Mi Dosis'",
        "status": "active",
        "version": "2.0.0",
        "features": [
            "Procesamiento de comandos 'Mi Dosis'",
            "Reconocimiento de medicamentos flexibles",
            "Extracción de dosis, frecuencia, hora y duración"
        ],
        "endpoints": {
            "process_command": "POST /api/voice/process-command",
            "process_dosis_command": "POST /api/voice/process-dosis-command",
            "test_parser": "POST /api/voice/test-parser",
            "health": "GET /health"
        }
    }

@app.get("/health")
async def health():
    parser_status = "active" if "extract_medication_info" in globals() and not extract_medication_info.__module__.startswith("__main__") else "error"
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "parser": parser_status,
            "node_connection": "checking..."
        }
    }

@app.post("/api/voice/process-dosis-command")
async def process_dosis_command(request: DosisCommandRequest):
    """
    Procesar comando de voz estilo 'Mi Dosis'
    """
    try:
        logger.info(f"🎯 Procesando comando 'Mi Dosis': {request.transcript[:100]}...")
        
        # Usar el parser mejorado
        parsed_info = extract_medication_info(request.transcript)
        
        logger.info(f"✅ Información parseada: {parsed_info}")
        
        # Verificar si es realmente un comando Dosis
        if not parsed_info.get("is_dosis_command", False):
            logger.warning("⚠️ El comando fue marcado como Dosis pero el parser no lo detectó")
        
        # Si es agregar medicamento, programar en Node.js
        if parsed_info.get("action") == "add_medication" and parsed_info.get("medication"):
            
            # Calcular fechas basadas en la duración
            start_date = datetime.now()
            
            # Parsear duración si existe
            duration_days = 7  # Valor por defecto
            if parsed_info.get("duration"):
                duration_str = parsed_info["duration"]
                match = re.search(r"(\d+)\s*(días|día|semanas|semana|meses|mes)", duration_str.lower())
                if match:
                    num = int(match.group(1))
                    unit = match.group(2)
                    if "semana" in unit:
                        duration_days = num * 7
                    elif "mes" in unit:
                        duration_days = num * 30
                    else:
                        duration_days = num
            
            end_date = start_date + timedelta(days=duration_days)
            
            # Parsear hora si existe
            time_str = parsed_info.get("time", "08:00")
            
            # Preparar datos para Node.js
            medication_data = {
                "userId": request.userId,
                "medicamentoId": f"dosis_{int(datetime.now().timestamp())}",
                "nombre": parsed_info["medication"],
                "dosis": parsed_info.get("dosage", "1 tableta"),
                "frecuencia": parsed_info.get("frequency", "Diario"),
                "hora": time_str,
                "fechaInicio": start_date.isoformat(),
                "fechaFin": end_date.isoformat()
            }
            
            logger.info(f"📤 Enviando a Node.js: {medication_data}")
            
            try:
                # Programar notificaciones
                response = requests.post(
                    f"{NODE_SERVER_URL}/schedule-multiple-notifications",
                    json=medication_data,
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    return {
                        "success": True,
                        "is_dosis_command": True,
                        "message": f"✅ {parsed_info['medication']} agregado correctamente con 'Mi Dosis'",
                        "parsed_info": parsed_info,
                        "scheduled_notifications": result.get("programadas", 0),
                        "confidence": parsed_info.get("confidence", 0.0),
                        "details": {
                            "dosis": parsed_info.get("dosage", "1 tableta"),
                            "frecuencia": parsed_info.get("frequency", "Diario"),
                            "hora": time_str,
                            "desde": start_date.strftime("%d/%m/%Y"),
                            "hasta": end_date.strftime("%d/%m/%Y"),
                            "días": duration_days,
                            "confianza": f"{parsed_info.get('confidence', 0.0):.0%}"
                        }
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Error en servidor Node.js: {response.status_code}",
                        "parsed_info": parsed_info
                    }
                    
            except Exception as e:
                logger.error(f"Error conectando con Node.js: {e}")
                return {
                    "success": False,
                    "message": f"Error de conexión: {str(e)}",
                    "parsed_info": parsed_info,
                    "fallback": True
                }
        
        # Para otros comandos Dosis
        elif parsed_info.get("action") == "list_medications":
            return {
                "success": True,
                "is_dosis_command": True,
                "message": "Mostrando lista de medicamentos desde 'Mi Dosis'...",
                "parsed_info": parsed_info
            }
        
        elif parsed_info.get("action") == "delete_medication":
            medication_name = parsed_info.get("medication", "medicamento")
            return {
                "success": True,
                "is_dosis_command": True,
                "message": f"Eliminando {medication_name} desde 'Mi Dosis'...",
                "parsed_info": parsed_info
            }
        
        else:
            return {
                "success": False,
                "is_dosis_command": True,
                "message": "No entendí completamente el comando 'Mi Dosis'.",
                "parsed_info": parsed_info,
                "suggestions": [
                    "Mi Dosis agregame [medicamento] de [dosis] a las [hora] con frecuencia [frecuencia] por [días] días",
                    "Dosis necesito [medicamento] [dosis] cada [horas] horas por [semanas] semanas",
                    "Asistente añádeme [medicamento] en la [mañana/tarde/noche] diario por [meses] meses"
                ]
            }
            
    except Exception as e:
        logger.error(f"Error procesando comando Dosis: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.post("/api/voice/process-command")
async def process_voice_command(request: VoiceCommandRequest):
    """
    Procesar comando de voz normal (no-Dosis)
    """
    try:
        logger.info(f"Procesando comando: {request.text}")
        
        # Usar el parser mejorado
        parsed_info = extract_medication_info(request.text)
        
        logger.info(f"Información parseada: {parsed_info}")
        
        # Si es agregar medicamento, programar en Node.js
        if parsed_info.get("action") == "add_medication" and parsed_info.get("medication"):
            
            # Calcular fechas
            start_date = datetime.now()
            duration_days = 7  # Valor por defecto
            if parsed_info.get("duration"):
                duration_str = parsed_info["duration"]
                match = re.search(r"(\d+)\s*(días|día)", duration_str.lower())
                if match:
                    duration_days = int(match.group(1))
            
            end_date = start_date + timedelta(days=duration_days)
            
            # Preparar datos para Node.js
            medication_data = {
                "userId": request.user_id,
                "medicamentoId": f"voice_{int(datetime.now().timestamp())}",
                "nombre": parsed_info["medication"],
                "dosis": parsed_info.get("dosage", "1 tableta"),
                "frecuencia": parsed_info.get("frequency", "Diario"),
                "hora": parsed_info.get("time", "08:00"),
                "fechaInicio": start_date.isoformat(),
                "fechaFin": end_date.isoformat()
            }
            
            logger.info(f"Enviando a Node.js: {medication_data}")
            
            try:
                # Programar notificaciones
                response = requests.post(
                    f"{NODE_SERVER_URL}/schedule-multiple-notifications",
                    json=medication_data,
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    return {
                        "success": True,
                        "is_dosis_command": parsed_info.get("is_dosis_command", False),
                        "message": f"✅ {parsed_info['medication']} programado correctamente",
                        "parsed_info": parsed_info,
                        "scheduled_notifications": result.get("programadas", 0),
                        "details": {
                            "dosis": parsed_info.get("dosage", "1 tableta"),
                            "frecuencia": parsed_info.get("frequency", "Diario"),
                            "hora": parsed_info.get("time", "08:00"),
                            "desde": start_date.strftime("%d/%m/%Y"),
                            "hasta": end_date.strftime("%d/%m/%Y"),
                            "días": duration_days
                        }
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Error en servidor Node.js: {response.status_code}",
                        "parsed_info": parsed_info
                    }
                    
            except Exception as e:
                logger.error(f"Error conectando con Node.js: {e}")
                return {
                    "success": False,
                    "message": f"Error de conexión: {str(e)}",
                    "parsed_info": parsed_info,
                    "fallback": True
                }
        
        # Para otros comandos
        elif parsed_info.get("action") == "list_medications":
            return {
                "success": True,
                "is_dosis_command": parsed_info.get("is_dosis_command", False),
                "message": "Mostrando lista de medicamentos...",
                "parsed_info": parsed_info
            }
        
        elif parsed_info.get("action") == "delete_medication":
            medication_name = parsed_info.get("medication", "medicamento")
            return {
                "success": True,
                "is_dosis_command": parsed_info.get("is_dosis_command", False),
                "message": f"Eliminando {medication_name}...",
                "parsed_info": parsed_info
            }
        
        else:
            return {
                "success": False,
                "is_dosis_command": parsed_info.get("is_dosis_command", False),
                "message": "No entendí el comando. Por favor intenta de nuevo.",
                "parsed_info": parsed_info,
                "suggestions": [
                    "Agregar paracetamol 500mg a las 8 de la mañana",
                    "Mi Dosis agregame ibuprofeno 400mg cada 8 horas por 7 días",
                    "Programar omeprazol cada 12 horas por 30 días"
                ]
            }
            
    except Exception as e:
        logger.error(f"Error procesando comando: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.post("/api/voice/test-parser")
async def test_parser(request: Dict[str, Any]):
    """
    Endpoint para probar el parser con diferentes comandos
    """
    try:
        text = request.get("text", "")
        examples = request.get("examples", False)
        
        if examples:
            # Generar ejemplos de prueba
            test_commands = [
                "Mi Dosis agregame paracetamol de 500 mg a las 8 de la mañana con frecuencia cada 12 horas por 14 días",
                "Dosis necesito ibuprofeno 400 mg cada 8 horas por 7 días",
                "Asistente añádeme omeprazol 20 mg en la noche diario por 30 días",
                "Agregar aspirina 100 mg después del desayuno",
                "¿Qué medicamentos tengo para hoy?",
                "Eliminar el paracetamol de mis recordatorios",
            ]
            
            results = []
            for cmd in test_commands:
                parsed = extract_medication_info(cmd)
                results.append({
                    "command": cmd,
                    "parsed": parsed,
                    "formatted": format_medication_response(parsed),
                    "success": parsed.get("medication") is not None or parsed.get("action") is not None
                })
            
            return {
                "success": True,
                "test_count": len(results),
                "results": results
            }
        
        else:
            # Probar un comando específico
            parsed = extract_medication_info(text)
            
            return {
                "success": True,
                "command": text,
                "parsed": parsed,
                "formatted": format_medication_response(parsed),
                "analysis": {
                    "has_medication": parsed.get("medication") is not None,
                    "has_action": parsed.get("action") is not None,
                    "is_dosis_command": parsed.get("is_dosis_command", False),
                    "confidence": parsed.get("confidence", 0.0),
                    "components_present": [
                        key for key in ["medication", "dosage", "frequency", "time", "duration"]
                        if parsed.get(key)
                    ]
                }
            }
            
    except Exception as e:
        logger.error(f"Error en test parser: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/medication/add")
async def add_medication(request: MedicationRequest):
    """Agregar medicamento manualmente (para pruebas)"""
    try:
        # Enviar al servidor Node.js
        medication_data = {
            "userId": request.user_id,
            "medicamentoId": f"manual_{int(datetime.now().timestamp())}",
            "nombre": request.nombre,
            "dosis": request.dosis,
            "frecuencia": request.frecuencia,
            "hora": request.hora,
            "fechaInicio": request.fecha_inicio,
            "fechaFin": request.fecha_fin
        }
        
        response = requests.post(
            f"{NODE_SERVER_URL}/schedule-multiple-notifications",
            json=medication_data,
            timeout=10
        )
        
        return {
            "success": response.status_code == 200,
            "node_response": response.json(),
            "data_sent": medication_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def start_server():
    """Función para iniciar el servidor"""
    import uvicorn
    
    logger.info("=" * 60)
    logger.info("🚀 INICIANDO ASISTENTE DE VOZ CON 'MI DOSIS'")
    logger.info("=" * 60)
    logger.info(f"📡 URL: http://localhost:8000")
    logger.info(f"📖 Docs: http://localhost:8000/docs")
    logger.info(f"🔗 Node.js: {NODE_SERVER_URL}")
    logger.info("\n🎯 Comandos 'Mi Dosis' de ejemplo:")
    logger.info('  POST /api/voice/process-dosis-command')
    logger.info('  Body: {"userId": "123", "transcript": "Mi Dosis agregame paracetamol...", "is_dosis_command": true}')
    logger.info("\n🔧 Endpoints de prueba:")
    logger.info('  POST /api/voice/test-parser')
    logger.info('  Body: {"text": "Mi Dosis agregame...", "examples": true}')
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    start_server()