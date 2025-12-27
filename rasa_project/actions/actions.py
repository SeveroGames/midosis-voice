"""
Acciones personalizadas para Rasa
"""
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, ReminderScheduled, ReminderCancelled
from datetime import datetime, timedelta
import sqlite3
import logging
import json
import os

logger = logging.getLogger(__name__)

# Base de datos para medicamentos
DB_PATH = os.path.join(os.path.dirname(__file__), "medicamentos.db")

def init_database():
    """Inicializar base de datos de medicamentos"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabla de medicamentos comunes
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS medicamentos (
        id INTEGER PRIMARY KEY,
        nombre TEXT NOT NULL,
        dosis_habitual TEXT,
        frecuencia TEXT,
        indicaciones TEXT,
        efectos_secundarios TEXT
    )
    ''')
    
    # Tabla de recordatorios del usuario
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS recordatorios (
        id INTEGER PRIMARY KEY,
        medicamento TEXT NOT NULL,
        hora TEXT NOT NULL,
        dias TEXT,
        activo INTEGER DEFAULT 1,
        usuario_id TEXT DEFAULT 'default'
    )
    ''')
    
    # Tabla de registro de tomas
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tomas_registradas (
        id INTEGER PRIMARY KEY,
        medicamento TEXT NOT NULL,
        fecha TEXT NOT NULL,
        hora TEXT NOT NULL,
        confirmada INTEGER DEFAULT 0,
        usuario_id TEXT DEFAULT 'default'
    )
    ''')
    
    # Insertar medicamentos comunes si no existen
    medicamentos_comunes = [
        ("metformina", "500mg", "Cada 12 horas", "Diabetes tipo 2", "Malestar estomacal, diarrea"),
        ("lisinopril", "10mg", "Una vez al día", "Hipertensión", "Tos seca, mareos"),
        ("atorvastatina", "20mg", "Noche", "Colesterol alto", "Dolor muscular"),
        ("omeprazol", "20mg", "Mañana antes de desayuno", "Acidez estomacal", "Dolor de cabeza"),
        ("losartán", "50mg", "Una vez al día", "Hipertensión", "Mareos, fatiga"),
        ("amlodipino", "5mg", "Una vez al día", "Hipertensión", "Hinchazón de tobillos"),
        ("paracetamol", "500mg", "Cada 8 horas si duele", "Dolor y fiebre", "Riesgo hepático en dosis altas"),
        ("ibuprofeno", "400mg", "Cada 8 horas si duele", "Dolor e inflamación", "Malestar estomacal")
    ]
    
    for med in medicamentos_comunes:
        cursor.execute(
            "SELECT 1 FROM medicamentos WHERE nombre = ?",
            (med[0],)
        )
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO medicamentos (nombre, dosis_habitual, frecuencia, indicaciones, efectos_secundarios) VALUES (?, ?, ?, ?, ?)",
                med
            )
    
    conn.commit()
    conn.close()
    logger.info("Base de datos de medicamentos inicializada")

class ActionVerificarToma(Action):
    """Verificar si el usuario tomó su medicamento"""
    
    def name(self) -> Text:
        return "action_verificar_toma"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            # Inicializar DB si no existe
            init_database()
            
            medicamento = tracker.get_slot("medicamento")
            hoy = datetime.now().strftime("%Y-%m-%d")
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            if medicamento:
                # Buscar si ya tomó este medicamento hoy
                cursor.execute(
                    "SELECT 1 FROM tomas_registradas WHERE medicamento = ? AND fecha = ?",
                    (medicamento, hoy)
                )
                
                if cursor.fetchone():
                    response = f"Sí, según mis registros ya tomaste {medicamento} hoy."
                else:
                    # Verificar información del medicamento
                    cursor.execute(
                        "SELECT frecuencia FROM medicamentos WHERE nombre = ?",
                        (medicamento.lower(),)
                    )
                    frecuencia = cursor.fetchone()
                    
                    if frecuencia:
                        response = f"No encuentro registro de que hayas tomado {medicamento} hoy. Normalmente se toma {frecuencia[0]}."
                    else:
                        response = f"No encuentro registro de que hayas tomado {medicamento} hoy. ¿Lo tomaste?"
                    
                    # Preguntar si quiere registrar la toma
                    dispatcher.utter_message(text=response)
                    dispatcher.utter_message(text="¿Quieres que registre que lo tomaste ahora?")
                    return [SlotSet("ultima_toma", "pendiente")]
            else:
                # Listar medicamentos del día
                cursor.execute(
                    "SELECT DISTINCT medicamento FROM tomas_registradas WHERE fecha = ?",
                    (hoy,)
                )
                tomas_hoy = cursor.fetchall()
                
                if tomas_hoy:
                    medicamentos = ", ".join([t[0] for t in tomas_hoy])
                    response = f"Hoy has tomado: {medicamentos}"
                else:
                    response = "No hay registros de medicamentos tomados hoy."
            
            conn.close()
            dispatcher.utter_message(text=response)
            
        except Exception as e:
            logger.error(f"Error en verificación de toma: {e}")
            dispatcher.utter_message(
                text="Tuve un problema consultando los registros. Por favor, intenta de nuevo."
            )
        
        return []

class ActionProgramarRecordatorio(Action):
    """Programar recordatorio para tomar medicamento"""
    
    def name(self) -> Text:
        return "action_programar_recordatorio"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            init_database()
            
            medicamento = tracker.get_slot("medicamento")
            hora = tracker.get_slot("hora_recordatorio")
            
            if not medicamento:
                dispatcher.utter_message(text="¿Para qué medicamento quieres el recordatorio?")
                return []
            
            if not hora:
                dispatcher.utter_message(text="¿A qué hora quieres que te recuerde?")
                return []
            
            # Guardar en base de datos
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO recordatorios (medicamento, hora, activo) VALUES (?, ?, 1)",
                (medicamento, hora)
            )
            
            conn.commit()
            conn.close()
            
            response = f"✅ Recordatorio programado: {medicamento} a las {hora}"
            dispatcher.utter_message(text=response)
            
            # Aquí podrías integrar con un sistema real de notificaciones
            
        except Exception as e:
            logger.error(f"Error programando recordatorio: {e}")
            dispatcher.utter_message(
                text="No pude programar el recordatorio. Por favor, intenta de nuevo."
            )
        
        return []

class ActionConsultarMedicamento(Action):
    """Proporcionar información sobre un medicamento"""
    
    def name(self) -> Text:
        return "action_consultar_medicamento"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            init_database()
            
            medicamento = tracker.get_slot("medicamento")
            
            if not medicamento:
                dispatcher.utter_message(text="¿De qué medicamento te gustaría información?")
                return []
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT dosis_habitual, frecuencia, indicaciones, efectos_secundarios FROM medicamentos WHERE nombre = ?",
                (medicamento.lower(),)
            )
            
            resultado = cursor.fetchone()
            conn.close()
            
            if resultado:
                dosis, frecuencia, indicaciones, efectos = resultado
                
                response = (
                    f"📋 Información de {medicamento.capitalize()}:\n"
                    f"• Dosis habitual: {dosis}\n"
                    f"• Frecuencia: {frecuencia}\n"
                    f"• Uso: {indicaciones}\n"
                    f"• Efectos secundarios comunes: {efectos}\n\n"
                    f"⚠️ Recuerda: Siempre consulta a tu médico."
                )
            else:
                response = (
                    f"No tengo información detallada sobre {medicamento}.\n"
                    f"Por favor, consulta con tu médico o farmacéutico."
                )
            
            dispatcher.utter_message(text=response)
            
        except Exception as e:
            logger.error(f"Error consultando medicamento: {e}")
            dispatcher.utter_message(
                text="No pude obtener la información del medicamento. Por favor, intenta de nuevo."
            )
        
        return []

class ActionEmergencia(Action):
    """Manejar situaciones de emergencia"""
    
    def name(self) -> Text:
        return "action_emergencia"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        response = (
            "🚨 **EMERGENCIA MÉDICA** 🚨\n\n"
            "1. **NO ESPERES** - Esto es serio\n"
            "2. **LLAMA AL 911** inmediatamente\n"
            "3. Si estás solo, contacta a un vecino o familiar\n"
            "4. Quédate en un lugar seguro\n"
            "5. Ten a la mano tus medicamentos\n\n"
            "⚠️ Yo soy solo un asistente virtual. Necesitas atención médica REAL."
        )
        
        dispatcher.utter_message(text=response)
        
        # También podrías enviar alertas a contactos de emergencia aquí
        
        return []

# Inicializar base de datos al importar
init_database()