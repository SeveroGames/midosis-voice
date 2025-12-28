"""
Actions específicas para comandos 'Mi Dosis'
"""
import logging
import json
import requests
from typing import Dict, Text, Any, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

logger = logging.getLogger(__name__)

# URL de tu backend FastAPI
FASTAPI_URL = "http://localhost:8000"

class ActionMiDosisAgregar(Action):
    """Acción para agregar medicamento desde comando 'Mi Dosis'"""
    
    def name(self) -> Text:
        return "action_mi_dosis_agregar"
    
    async def run(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            # Extraer información de los slots
            medicamento = tracker.get_slot("medicamento")
            dosis = tracker.get_slot("dosis_valor")
            hora = tracker.get_slot("hora_recordatorio")
            frecuencia = tracker.get_slot("frecuencia_toma")
            duracion = tracker.get_slot("duracion_tratamiento")
            
            # Verificar información mínima
            if not medicamento:
                dispatcher.utter_message(
                    text="Necesito saber qué medicamento quieres agregar."
                )
                return []
            
            # Construir comando de texto para el parser
            command_parts = []
            
            if medicamento:
                command_parts.append(f"agregar {medicamento}")
            
            if dosis:
                command_parts.append(f"{dosis}")
            
            if hora:
                command_parts.append(f"a las {hora}")
            
            if frecuencia:
                command_parts.append(f"con frecuencia {frecuencia}")
            
            if duracion:
                command_parts.append(f"por {duracion}")
            
            command_text = " ".join(command_parts)
            
            # Enviar al backend FastAPI
            payload = {
                "text": command_text,
                "user_id": tracker.sender_id  # ID único del usuario
            }
            
            response = requests.post(
                f"{FASTAPI_URL}/api/voice/process-command",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get("success"):
                    # Extraer información para confirmación
                    parsed_info = result.get("parsed_info", {})
                    
                    # Enviar mensaje de confirmación
                    confirmation_message = (
                        f"✅ {parsed_info.get('medication', medicamento)} agregado correctamente.\n"
                        f"• Dosis: {parsed_info.get('dosage', dosis or '1 tableta')}\n"
                        f"• Hora: {parsed_info.get('time', hora or '08:00')}\n"
                        f"• Frecuencia: {parsed_info.get('frequency', frecuencia or 'Diario')}\n"
                        f"• Duración: {parsed_info.get('duration', duracion or '7 días')}"
                    )
                    
                    dispatcher.utter_message(text=confirmation_message)
                    
                    # Registrar en logs
                    logger.info(f"Medicamento agregado: {medicamento} para usuario {tracker.sender_id}")
                    
                else:
                    dispatcher.utter_message(
                        text=f"Hubo un error: {result.get('message', 'Error desconocido')}"
                    )
            
            else:
                dispatcher.utter_message(
                    text="Lo siento, hubo un problema de conexión con el servidor."
                )
            
            # Limpiar slots después de procesar
            return [
                SlotSet("medicamento", None),
                SlotSet("dosis_valor", None),
                SlotSet("hora_recordatorio", None),
                SlotSet("frecuencia_toma", None),
                SlotSet("duracion_tratamiento", None),
            ]
            
        except Exception as e:
            logger.error(f"Error en action_mi_dosis_agregar: {e}")
            dispatcher.utter_message(
                text="Lo siento, ocurrió un error procesando tu solicitud."
            )
            return []

class ActionMiDosisListar(Action):
    """Acción para listar medicamentos del usuario"""
    
    def name(self) -> Text:
        return "action_mi_dosis_listar"
    
    async def run(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            # Consultar medicamentos del usuario
            user_id = tracker.sender_id
            
            # En un sistema real, aquí consultarías la base de datos
            # Por ahora simulamos una respuesta
            
            # Para integración real, conectar con tu backend
            response = requests.get(
                f"{FASTAPI_URL}/api/user/{user_id}/medications",
                timeout=10
            )
            
            if response.status_code == 200:
                medications = response.json().get("medications", [])
                
                if medications:
                    medication_list = "\n".join([
                        f"• {med['nombre']} - {med.get('dosis', '')} "
                        f"({med.get('frecuencia', '')} a las {med.get('hora', '')})"
                        for med in medications[:5]  # Mostrar máximo 5
                    ])
                    
                    message = f"📋 Tus medicamentos:\n{medication_list}"
                    
                    if len(medications) > 5:
                        message += f"\n\n... y {len(medications) - 5} más."
                    
                else:
                    message = "No tienes medicamentos programados actualmente."
                
                dispatcher.utter_message(text=message)
            
            else:
                # Respuesta simulada para desarrollo
                sample_meds = [
                    {"nombre": "Paracetamol", "dosis": "500 mg", "frecuencia": "Cada 8 horas", "hora": "08:00"},
                    {"nombre": "Omeprazol", "dosis": "20 mg", "frecuencia": "Diario", "hora": "20:00"},
                    {"nombre": "Ibuprofeno", "dosis": "400 mg", "frecuencia": "Cuando sea necesario", "hora": "00:00"},
                ]
                
                medication_list = "\n".join([
                    f"• {med['nombre']} - {med['dosis']} ({med['frecuencia']} a las {med['hora']})"
                    for med in sample_meds
                ])
                
                dispatcher.utter_message(
                    text=f"📋 Tus medicamentos (ejemplo):\n{medication_list}\n\n"
                         f"Nota: Esta es una lista de ejemplo. En producción se conectaría a tu base de datos."
                )
            
            return []
            
        except Exception as e:
            logger.error(f"Error en action_mi_dosis_listar: {e}")
            
            # Respuesta de fallback
            dispatcher.utter_message(
                text="Actualmente tienes medicamentos como Paracetamol, Omeprazol e Ibuprofeno programados. "
                     "Para ver la lista completa, consulta la aplicación principal."
            )
            return []

class ActionMiDosisEliminar(Action):
    """Acción para eliminar medicamento"""
    
    def name(self) -> Text:
        return "action_mi_dosis_eliminar"
    
    async def run(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            medicamento = tracker.get_slot("medicamento")
            
            if not medicamento:
                dispatcher.utter_message(
                    text="Necesito saber qué medicamento quieres eliminar."
                )
                return []
            
            # En un sistema real, aquí llamarías a la API para eliminar
            # Simulamos la eliminación
            
            dispatcher.utter_message(
                text=f"✅ {medicamento} ha sido eliminado de tu lista de medicamentos."
            )
            
            logger.info(f"Medicamento eliminado: {medicamento} para usuario {tracker.sender_id}")
            
            # Limpiar slot
            return [SlotSet("medicamento", None)]
            
        except Exception as e:
            logger.error(f"Error en action_mi_dosis_eliminar: {e}")
            dispatcher.utter_message(
                text="Lo siento, ocurrió un error eliminando el medicamento."
            )
            return []