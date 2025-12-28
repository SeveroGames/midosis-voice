import spacy
import re
from datetime import datetime

class MedicationParser:
    def __init__(self):
        """Cargar modelo de spaCy para español"""
        try:
            # Cargar modelo de español
            self.nlp = spacy.load("es_core_news_sm")
        except:
            print("Modelo spaCy no encontrado. Ejecuta: python -m spacy download es_core_news_sm")
            self.nlp = None
    
    def extract_info(self, text):
        """Extraer información de medicamentos del texto"""
        if not self.nlp:
            return self._regex_extraction(text)
        
        doc = self.nlp(text.lower())
        
        info = {
            "medication": None,
            "dosage": None,
            "time": None,
            "frequency": None,
            "action": None,
            "duration": None,
            "confidence": 0.0,
            "is_dosis_command": False
        }
        
        # Detectar si es comando "Mi Dosis"
        dosis_patterns = [
            r"mi dosis",
            r"dosis,?\s",
            r"asistente dosis",
            r"hey dosis"
        ]
        
        for pattern in dosis_patterns:
            if re.search(pattern, text.lower()):
                info["is_dosis_command"] = True
                break
        
        # Patrones comunes
        patterns = {
            "medication": [
                r"medicina\s+(\w+)",
                r"medicamento\s+(\w+)",
                r"pastilla\s+(?:de\s+)?(\w+)",
                r"tomar\s+(\w+)",
                r"agregar\s+(\w+)",
                r"añadir\s+(\w+)"
            ],
            "dosage": [
                r"(\d+)\s*(mg|ml|g|mg|miligramos|mililitros|tableta|tabletas|cápsula|cápsulas)",
                r"dosis de\s+(\d+)\s*(mg|ml|g)",
                r"(\d+)\s*(comprimidos?|pastillas?|cápsulas?)"
            ],
            "time": [
                r"a\s+las\s+(\d{1,2}:\d{2})",
                r"(\d{1,2})\s*(?:de la\s+)?(mañana|tarde|noche)",
                r"cada\s+(\d+)\s+horas",
                r"en la (mañana|tarde|noche)"
            ],
            "frequency": [
                r"cada\s+(\d+)\s*(horas|días)",
                r"(\d+)\s*veces al día",
                r"diario|todos los días",
                r"semanal|una vez por semana"
            ],
            "duration": [
                r"por\s+(\d+)\s*(días|día|semanas|semana|meses|mes)",
                r"durante\s+(\d+)\s*(días|día)",
                r"para\s+(\d+)\s*(días|día)"
            ]
        }
        
        # Extraer con regex
        for key, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, text.lower())
                if match:
                    if key == "time" and len(match.groups()) > 1 and match.group(2):
                        info[key] = f"{match.group(1)} {match.group(2)}"
                    elif key == "duration":
                        info[key] = f"{match.group(1)} {match.group(2)}"
                    else:
                        info[key] = match.group(1)
                    break
        
        # Determinar acción solicitada
        action_keywords = {
            "tomé": "verificar",
            "tomo": "verificar",
            "tomar": "recordatorio",
            "agregar": "add_medication",
            "añadir": "add_medication",
            "poner": "add_medication",
            "programar": "add_medication",
            "eliminar": "delete_medication",
            "quitar": "delete_medication",
            "borrar": "delete_medication",
            "listar": "list_medications",
            "mostrar": "list_medications",
            "ver": "list_medications",
            "olvidé": "recordatorio",
            "recordar": "recordatorio",
            "recordarme": "recordatorio",
            "dosis": "information",
            "información": "information"
        }
        
        for keyword, action in action_keywords.items():
            if keyword in text.lower():
                info["action"] = action
                break
        
        # Calcular confianza basada en los elementos encontrados
        found_elements = sum(1 for key in ["medication", "dosage", "time", "frequency", "duration"] if info[key])
        info["confidence"] = found_elements / 5.0
        
        return info
    
    def _regex_extraction(self, text):
        """Extracción básica con regex si spaCy no está disponible"""
        info = {
            "medication": None,
            "dosage": None,
            "time": None,
            "frequency": None,
            "action": None,
            "duration": None,
            "confidence": 0.0,
            "is_dosis_command": False
        }
        
        # Patrones simples
        med_match = re.search(r"(?:medicina|medicamento|pastilla)\s+(\w+)", text.lower())
        if med_match:
            info["medication"] = med_match.group(1).capitalize()
        
        # Detectar "Mi Dosis"
        if re.search(r"mi dosis|dosis,", text.lower()):
            info["is_dosis_command"] = True
        
        return info


def format_medication_response(parsed_info):
    """Formatear la respuesta del parser para mostrarla al usuario"""
    if not parsed_info.get("medication") and not parsed_info.get("action"):
        return "No pude identificar el medicamento o la acción solicitada."
    
    response_parts = []
    
    if parsed_info.get("is_dosis_command"):
        response_parts.append("🩺 Comando 'Mi Dosis' detectado")
    
    if parsed_info.get("action"):
        action_map = {
            "add_medication": "Agregar medicamento",
            "delete_medication": "Eliminar medicamento",
            "list_medications": "Listar medicamentos",
            "verificar": "Verificar toma",
            "recordatorio": "Crear recordatorio",
            "information": "Información"
        }
        response_parts.append(f"📋 Acción: {action_map.get(parsed_info['action'], parsed_info['action'])}")
    
    if parsed_info.get("medication"):
        response_parts.append(f"💊 Medicamento: {parsed_info['medication']}")
    
    if parsed_info.get("dosage"):
        response_parts.append(f"📏 Dosis: {parsed_info['dosage']}")
    
    if parsed_info.get("time"):
        response_parts.append(f"⏰ Hora: {parsed_info['time']}")
    
    if parsed_info.get("frequency"):
        response_parts.append(f"🔄 Frecuencia: {parsed_info['frequency']}")
    
    if parsed_info.get("duration"):
        response_parts.append(f"📅 Duración: {parsed_info['duration']}")
    
    if parsed_info.get("confidence", 0) > 0:
        response_parts.append(f"🎯 Confianza: {parsed_info['confidence']:.0%}")
    
    return "\n".join(response_parts)


# Instancia global
parser = MedicationParser()

def extract_medication_info(text):
    """Función para usar desde otros módulos"""
    return parser.extract_info(text)


if __name__ == "__main__":
    # Prueba del parser
    test_commands = [
        "Mi Dosis agregame paracetamol de 500 mg a las 8 de la mañana con frecuencia cada 12 horas por 14 días",
        "Dosis necesito ibuprofeno 400 mg cada 8 horas por 7 días",
        "Agregar omeprazol 20 mg en la noche diario por 30 días",
        "¿Qué medicamentos tengo para hoy?",
        "Eliminar el paracetamol de mis recordatorios",
    ]
    
    print("🔬 Probando MedicationParser...")
    print("=" * 80)
    
    for cmd in test_commands:
        print(f"\n📝 Comando: {cmd}")
        result = extract_medication_info(cmd)
        print(f"🧠 Resultado parseado: {result}")
        print(f"📄 Formateado:\n{format_medication_response(result)}")
        print("-" * 80)