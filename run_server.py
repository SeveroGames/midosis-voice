#!/usr/bin/env python
"""
Script principal para ejecutar el servidor con verificación previa
"""
import sys
import os
from pathlib import Path
import logging
import socket

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment():
    """Verificar entorno y dependencias"""
    logger.info("Verificando entorno...")
    
    # Verificar Python 3.10
    python_version = sys.version_info
    if not (python_version.major == 3 and python_version.minor == 10):
        logger.error(f"Se requiere Python 3.10. Tienes {python_version.major}.{python_version.minor}")
        logger.error("Descarga Python 3.10.11 desde: https://www.python.org/downloads/release/python-31011/")
        return False
    
    # Verificar entorno virtual
    venv_backend = Path("venv_backend")
    if not (venv_backend.exists() or "VIRTUAL_ENV" in os.environ):
        logger.warning("No se detectó entorno virtual activo.")
        logger.warning("Ejecuta primero: venv_backend\\Scripts\\activate")
        return False
    
    # Verificar dependencias críticas
    critical_modules = ["fastapi", "uvicorn", "torch", "whisper", "TTS", "spacy"]
    
    for module in critical_modules:
        try:
            __import__(module)
            logger.info(f"✓ {module}")
        except ImportError as e:
            logger.error(f"✗ {module} no encontrado: {e}")
            logger.error("Ejecuta: pip install -r requirements_backend.txt")
            return False
    
    return True

def check_ports():
    """Verificar puertos disponibles"""
    ports = [8000]  # Solo verificar puerto del backend
    
    for port in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('localhost', port))
            sock.close()
            logger.info(f"✓ Puerto {port} disponible")
        except socket.error:
            logger.warning(f"⚠ Puerto {port} en uso. Matando proceso...")
            # Intentar liberar el puerto
            try:
                import subprocess
                result = subprocess.run(
                    f"netstat -ano | findstr :{port}",
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if result.stdout:
                    pid = result.stdout.strip().split()[-1]
                    subprocess.run(f"taskkill /PID {pid} /F", shell=True)
                    logger.info(f"Proceso {pid} terminado")
            except:
                pass
    
    return True

def check_rasa_status():
    """Verificar si Rasa está corriendo"""
    import requests
    
    try:
        response = requests.get("http://localhost:5005", timeout=2)
        if response.status_code < 500:
            logger.info("✓ Rasa API detectado en puerto 5005")
            return True
    except:
        logger.warning("⚠ Rasa API no detectado en puerto 5005")
        logger.warning("Ejecuta en otra terminal: cd rasa_project && ..\\venv_rasa\\Scripts\\activate && rasa run --enable-api --cors '*' --port 5005")
        return False

def print_banner():
    """Mostrar banner informativo"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║              ASISTENTE DE VOZ PARA ADULTOS MAYORES          ║
    ║                      BACKEND SERVER                         ║
    ╚══════════════════════════════════════════════════════════════╝
    
    🎯 Objetivo: Procesamiento de voz y conversaciones naturales
    🔧 Módulos: STT (Whisper) | TTS (Coqui) | NLP (spaCy)
    🌐 API: FastAPI en http://localhost:8000
    📱 Frontend: Flutter app para Android/iOS
    
    """
    print(banner)

def main():
    """Función principal"""
    print_banner()
    
    # Verificar entorno
    if not check_environment():
        sys.exit(1)
    
    # Verificar puertos
    check_ports()
    
    # Verificar Rasa (solo verificar, no iniciar)
    check_rasa_status()
    
    # Importar y ejecutar servidor
    try:
        # Cambiar al directorio api
        api_dir = Path("api")
        if not api_dir.exists():
            logger.error("Directorio 'api' no encontrado")
            sys.exit(1)
        
        # Importar servidor
        sys.path.insert(0, str(api_dir.parent))
        
        from api.server import start_server
        
        logger.info("\n" + "="*60)
        logger.info("INICIANDO SERVIDOR FASTAPI")
        logger.info("="*60)
        
        # Mostrar URLs importantes
        print("\n📊 URLs de acceso:")
        print("   Backend API:    http://localhost:8000")
        print("   Documentación:  http://localhost:8000/docs")
        print("   Estado:         http://localhost:8000/health")
        print("\n🎤 Endpoints principales:")
        print("   POST /api/transcribe   - Transcribir audio")
        print("   POST /api/tts          - Texto a voz")
        print("   GET  /audio/{file}     - Obtener audio")
        print("   POST /api/process      - Procesar texto con Rasa")
        print("\n📱 Para conectar Flutter:")
        print("   Usa esta IP: http://192.168.56.1:8000")
        print("\n⚠️  IMPORTANTE: Rasa debe estar ejecutándose por separado")
        print("   1. Terminal 1: rasa run actions --port 5055")
        print("   2. Terminal 2: rasa run --enable-api --port 5005")
        print("\n🔄 Servidor iniciando...")
        
        # Iniciar servidor
        start_server()
        
    except KeyboardInterrupt:
        logger.info("\nServidor detenido por el usuario")
    except Exception as e:
        logger.error(f"Error iniciando servidor: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()