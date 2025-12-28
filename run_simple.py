#!/usr/bin/env python
"""
Ejecutar servidor de forma simple
"""
import subprocess
import sys

print("🚀 Iniciando servidor FastAPI...")
print("📡 URL: http://localhost:8000")
print("📖 Docs: http://localhost:8000/docs")
print("\n🔄 Presiona Ctrl+C para detener\n")

# Comando para ejecutar Uvicorn
cmd = [
    sys.executable,
    "-m", "uvicorn",
    "api.server:app",
    "--host", "0.0.0.0",
    "--port", "8000",
    "--reload"
]

try:
    subprocess.run(cmd)
except KeyboardInterrupt:
    print("\n👋 Servidor detenido")