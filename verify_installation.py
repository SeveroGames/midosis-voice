import sys
import importlib
import pkg_resources
import platform
import torch

def print_header(text):
    print("\n" + "="*60)
    print(f" {text}")
    print("="*60)

def check_module(module_name, min_version=None):
    try:
        module = importlib.import_module(module_name)
        version = getattr(module, '__version__', 'Desconocida')
        
        if min_version:
            if pkg_resources.parse_version(version) >= pkg_resources.parse_version(min_version):
                status = "✓"
            else:
                status = "⚠"
        else:
            status = "✓"
        
        print(f"{status} {module_name:20} v{version}")
        return True
        
    except ImportError:
        print(f"✗ {module_name:20} NO INSTALADO")
        return False

def check_system():
    print_header("INFORMACIÓN DEL SISTEMA")
    
    print(f"Sistema: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    print(f"Arquitectura: {platform.architecture()[0]}")
    
    # Verificar CUDA
    cuda_available = torch.cuda.is_available()
    print(f"CUDA disponible: {'✓' if cuda_available else '✗'}")
    
    if cuda_available:
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"Memoria GPU: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

def check_modules():
    print_header("MÓDULOS INSTALADOS")
    
    modules = [
        ("fastapi", "0.104.0"),
        ("uvicorn", "0.24.0"),
        ("torch", "2.1.0"),
        ("whisper", None),
        ("TTS", "0.21.0"),
        ("spacy", "3.7.0"),
        ("numpy", "1.24.0"),
        ("requests", "2.31.0"),
    ]
    
    all_ok = True
    for module_name, min_version in modules:
        if not check_module(module_name, min_version):
            all_ok = False
    
    return all_ok

def check_directories():
    print_header("ESTRUCTURA DE DIRECTORIOS")
    
    import os
    from pathlib import Path
    
    directories = [
        ".",
        "./api",
        "./stt",
        "./tts",
        "./nlp",
        "./audio",
        "./rasa_project"
    ]
    
    all_ok = True
    for dir_path in directories:
        path = Path(dir_path)
        if path.exists():
            print(f"✓ {dir_path:20} Existe")
        else:
            print(f"✗ {dir_path:20} No existe")
            all_ok = False
    
    return all_ok

def check_imports():
    print_header("VERIFICACIÓN DE IMPORTS")
    
    imports_to_test = [
        "from fastapi import FastAPI",
        "import whisper",
        "from TTS.api import TTS",
        "import spacy",
        "import torch",
        "import numpy as np"
    ]
    
    all_ok = True
    for import_stmt in imports_to_test:
        try:
            # Usar exec para probar imports
            exec(import_stmt)
            print(f"✓ {import_stmt}")
        except Exception as e:
            print(f"✗ {import_stmt}")
            print(f"  Error: {e}")
            all_ok = False
    
    return all_ok

def main():
    print("🔍 VERIFICACIÓN COMPLETA DEL SISTEMA DE ASISTENTE DE VOZ")
    print("="*60)
    
    # Verificar sistema
    check_system()
    
    # Verificar módulos
    modules_ok = check_modules()
    
    # Verificar directorios
    dirs_ok = check_directories()
    
    # Verificar imports
    imports_ok = check_imports()
    
    # Resumen
    print_header("RESUMEN")
    
    if all([modules_ok, dirs_ok, imports_ok]):
        print("✅ SISTEMA LISTO PARA USAR")
        print("\nPara iniciar el servidor:")
        print("  python run_server.py")
        print("\nPara probar la API:")
        print("  curl http://localhost:8000/health")
    else:
        print("⚠️  SE DETECTARON PROBLEMAS")
        print("\nSugerencias:")
        if not modules_ok:
            print("  - Ejecuta: python install_dependencies.py")
        if not dirs_ok:
            print("  - Verifica la estructura de carpetas")
        if not imports_ok:
            print("  - Reinstala las dependencias problemáticas")
        
        print("\nComando para reinstalar todo:")
        print("  python install_dependencies.py --force")

if __name__ == "__main__":
    main()