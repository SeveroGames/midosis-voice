#!/usr/bin/env python3
"""
Script de instalación segura con verificación de compatibilidad
"""
import subprocess
import sys
import platform
import os
from pathlib import Path

def check_python_version():
    """Verificar que sea Python 3.10"""
    version = sys.version_info
    if version.major == 3 and version.minor == 10:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro} - OK")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor} detectado")
        print("Se requiere Python 3.10.11 exactamente")
        print("Descargar desde: https://www.python.org/downloads/release/python-31011/")
        return False

def run_command(cmd, description):
    """Ejecutar comando con manejo de errores"""
    print(f"\n{description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ {description} completado")
            return True
        else:
            print(f"✗ Error en {description}:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"✗ Error ejecutando {description}: {e}")
        return False

def main():
    print("=" * 60)
    print("INSTALADOR DE ASISTENTE DE VOZ - VERIFICACIÓN DE COMPATIBILIDAD")
    print("=" * 60)
    
    # 1. Verificar Python
    if not check_python_version():
        return
    
    # 2. Verificar sistema
    print(f"\nSistema: {platform.system()} {platform.release()}")
    
    # 3. Crear y activar entorno virtual
    print("\n1. Configurando entorno virtual...")
    if not os.path.exists("venv"):
        run_command("python -m venv venv", "Creando entorno virtual")
    
    # Determinar comando de activación según OS
    if platform.system() == "Windows":
        activate_cmd = "venv\\Scripts\\activate && "
        pip_cmd = "venv\\Scripts\\pip"
        python_cmd = "venv\\Scripts\\python"
    else:
        activate_cmd = "source venv/bin/activate && "
        pip_cmd = "venv/bin/pip"
        python_cmd = "venv/bin/python"
    
    # 4. Actualizar pip
    run_command(f"{pip_cmd} install --upgrade pip", "Actualizando pip")
    
    # 5. Instalar torch primero (es crítico para compatibilidad)
    print("\n2. Instalando PyTorch (requiere versión específica)...")
    
    # Instalar torch sin dependencias conflictivas primero
    torch_cmd = f"{pip_cmd} install torch==2.1.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cpu"
    if torch.cuda.is_available():
        torch_cmd = f"{pip_cmd} install torch==2.1.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cu118"
    
    run_command(torch_cmd, "Instalando PyTorch")
    
    # 6. Instalar requerimientos base
    print("\n3. Instalando dependencias principales...")
    
    # Crear requirements_temp.txt sin torch
    temp_reqs = [
        "fastapi==0.104.1",
        "uvicorn[standard]==0.24.0",
        "python-multipart==0.0.6",
        "numpy==1.24.3",
        "requests==2.31.0",
        "pydantic==2.5.0",
        "python-dotenv==1.0.0",
        "pyttsx3==2.90"
    ]
    
    with open("requirements_temp.txt", "w") as f:
        f.write("\n".join(temp_reqs))
    
    run_command(f"{pip_cmd} install -r requirements_temp.txt", "Instalando dependencias base")
    
    # 7. Instalar Whisper
    print("\n4. Instalando Whisper STT...")
    run_command(f"{pip_cmd} install openai-whisper==20231117", "Instalando Whisper")
    
    # 8. Instalar Coqui TTS
    print("\n5. Instalando Coqui TTS...")
    # Primero dependencias específicas
    tts_deps = [
        "librosa==0.10.1",
        "soundfile==0.12.1",
        "scipy==1.11.4"
    ]
    
    for dep in tts_deps:
        run_command(f"{pip_cmd} install {dep}", f"Instalando {dep}")
    
    # Luego TTS
    run_command(f"{pip_cmd} install TTS==0.21.2", "Instalando TTS")
    
    # 9. Instalar spaCy
    print("\n6. Instalando spaCy y modelo en español...")
    run_command(f"{pip_cmd} install spacy==3.7.2", "Instalando spaCy")
    
    # Modelo en español
    model_url = "https://github.com/explosion/spacy-models/releases/download/es_core_news_sm-3.7.0/es_core_news_sm-3.7.0-py3-none-any.whl"
    run_command(f"{pip_cmd} install {model_url}", "Instalando modelo español")
    
    # 10. Verificar instalaciones
    print("\n" + "=" * 60)
    print("VERIFICACIÓN FINAL DE INSTALACIONES")
    print("=" * 60)
    
    verification_commands = [
        (f"{python_cmd} -c \"import torch; print(f'Torch: {torch.__version__}')\"", "Torch"),
        (f"{python_cmd} -c \"import whisper; print('Whisper: OK')\"", "Whisper"),
        (f"{python_cmd} -c \"import TTS; print(f'TTS: {TTS.__version__}')\"", "TTS"),
        (f"{python_cmd} -c \"import spacy; print('spaCy: OK')\"", "spaCy"),
        (f"{python_cmd} -c \"import fastapi; print(f'FastAPI: {fastapi.__version__}')\"", "FastAPI"),
    ]
    
    all_ok = True
    for cmd, name in verification_commands:
        if run_command(cmd, f"Verificando {name}"):
            print(f"✓ {name} - Correcto")
        else:
            print(f"✗ {name} - Problema detectado")
            all_ok = False
    
    # 11. Limpiar
    if os.path.exists("requirements_temp.txt"):
        os.remove("requirements_temp.txt")
    
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ INSTALACIÓN COMPLETADA EXITOSAMENTE")
        print("\nPara activar el entorno virtual:")
        if platform.system() == "Windows":
            print("venv\\Scripts\\activate")
        else:
            print("source venv/bin/activate")
        print("\nPara ejecutar el servidor:")
        print("python run_server.py")
    else:
        print("⚠️  Se detectaron problemas en la instalación")
        print("Revisa los mensajes de error arriba")
    
    print("=" * 60)

if __name__ == "__main__":
    main()