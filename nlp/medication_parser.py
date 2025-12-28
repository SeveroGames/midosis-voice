import spacy
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

class MedicationParser:
    def __init__(self):
        """Cargar modelo de spaCy para español"""
        try:
            # Cargar modelo de español
            self.nlp = spacy.load("es_core_news_sm")
            print("✅ spaCy cargado correctamente")
        except Exception as e:
            print(f"⚠️ Modelo spaCy no encontrado: {e}")
            print("💡 Ejecuta: python -m spacy download es_core_news_sm")
            self.nlp = None
    
    def extract_info(self, text: str) -> Dict[str, Any]:
        """Extraer información de medicamentos del texto - VERSIÓN MEJORADA"""
        info = {
            "medication": None,
            "dosage": None,
            "time": None,
            "frequency": None,
            "action": None,
            "duration": None,
            "confidence": 0.0,
            "is_dosis_command": False,
            "raw_text": text
        }
        
        text_lower = text.lower()
        
        # 1. Detectar si es comando "Mi Dosis" (MEJORADO)
        dosis_patterns = [
            r"^mi dosis",
            r"\bmi dosis\b",
            r"^dosis\b",
            r"\bdosis\b",
            r"asistente dosis",
            r"hey dosis",
            r"hola dosis"
        ]
        
        for pattern in dosis_patterns:
            if re.search(pattern, text_lower):
                info["is_dosis_command"] = True
                break
        
        # 2. Determinar acción PRIMERO (CRÍTICO)
        action_patterns = {
            "add_medication": [
                r"\bagregar\b", r"\bagrégame\b", r"\bañadir\b", r"\bañádeme\b",
                r"\bponer\b", r"\bponme\b", r"\bprogramar\b", r"\bprogramame\b",
                r"\bnecesito\b", r"\bquiero\b", r"\bdeseo\b", r"\bpreciso\b",
                r"\bregistrar\b", r"\bregistrame\b"
            ],
            "delete_medication": [
                r"\beliminar\b", r"\bquitar\b", r"\bborrar\b", r"\bremover\b"
            ],
            "list_medications": [
                r"\blistar\b", r"\bmostrar\b", r"\bver\b", r"\bconsultar\b",
                r"\bqu[ée]\s+medicamentos", r"\bcu[áa]les"
            ],
            "check_today": [
                r"\bhoy\b", r"\bpara hoy\b", r"\bqu[ée]\s+tengo\b"
            ]
        }
        
        for action_type, patterns in action_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    info["action"] = action_type
                    break
            if info["action"]:
                break
        
        # Si no se encontró acción pero es comando Dosis, asumir add_medication
        if not info["action"] and info["is_dosis_command"]:
            info["action"] = "add_medication"
        
        # 3. Extraer medicamento (MÉTODO MEJORADO)
        info["medication"] = self._extract_medication_improved(text_lower, info["action"])
        
        # 4. Extraer dosis (PATRONES MEJORADOS) - CORREGIDO
        dosage_patterns = [
            r'(\d+)\s*(mg|g|ml|miligramos|mililitros|gramos|tableta|tabletas|cápsula|cápsulas|comprimido|comprimidos)',
            r'dosis\s+(?:de\s+)?(\d+)\s*(mg|g|ml)',
            r'(\d+)\s*(mg|g|ml)\s+(?:de\s+)?',
            r'tomar\s+(\d+)\s*(mg|g|ml|tableta)'
        ]
        
        for pattern in dosage_patterns:
            match = re.search(pattern, text_lower)
            # CORRECCIÓN: Verificar que match existe y tiene grupos
            if match and match.groups():
                cantidad = match.group(1)
                unidad = match.group(2) if len(match.groups()) > 1 else 'mg'
                info["dosage"] = f"{cantidad} {unidad}"
                break
        
        # 5. Extraer frecuencia (MEJORADO)
        frequency_map = {
            r'cada\s+8\s*(?:horas|hrs|h)': 'Cada 8 horas',
            r'cada\s+12\s*(?:horas|hrs|h)': 'Cada 12 horas',
            r'cada\s+24\s*(?:horas|hrs|h)': 'Diario',
            r'cada\s+d[ií]a|diario|todos los d[ií]as|una vez al d[ií]a': 'Diario',
            r'semanal|una vez por semana|cada semana': 'Semanal',
            r'\b8\s*horas\b': 'Cada 8 horas',
            r'\b12\s*horas\b': 'Cada 12 horas',
            r'tres veces al d[ií]a': 'Cada 8 horas',
            r'dos veces al d[ií]a': 'Cada 12 horas'
        }
        
        for pattern, freq in frequency_map.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                info["frequency"] = freq
                break
        
        # Si no se encontró frecuencia, usar valor por defecto según acción
        if not info["frequency"] and info["action"] == "add_medication":
            info["frequency"] = "Diario"
        
        # 6. Extraer hora - CORREGIDO
        time_patterns = [
            r'a las (\d{1,2})(?::(\d{2}))?\s*(?:de la\s+)?(mañana|tarde|noche|am|pm|a\.m\.|p\.m\.)?',
            r'(\d{1,2})\s*(?:de la\s+)?(mañana|tarde|noche)',
            r'(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)',
            r'en la (mañana|tarde|noche)',
            r'por la (mañana|tarde|noche)',
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, text_lower)
            # CORRECCIÓN: Verificar match y manejar grupos de forma segura
            if match:
                # Obtener grupos de forma segura
                groups = match.groups()
                hour = groups[0] if groups and groups[0] else "8"
                minute = groups[1] if len(groups) > 1 and groups[1] else "00"
                period = groups[2] if len(groups) > 2 and groups[2] else ""
                
                # Convertir a 24h si es necesario
                try:
                    hour_int = int(hour)
                    if period and ('tarde' in period or 'noche' in period or 'pm' in period or 'p.m.' in period):
                        if hour_int < 12:
                            hour_int += 12
                    elif period and ('mañana' in period or 'am' in period or 'a.m.' in period) and hour_int == 12:
                        hour_int = 0
                    
                    info["time"] = f"{hour_int:02d}:{minute}"
                    break
                except ValueError:
                    continue
        
        # 7. Extraer duración - CORREGIDO
        duration_patterns = [
            r'por\s+(\d+)\s*(d[ií]as|d[ií]a|semanas|semana|meses|mes)',
            r'durante\s+(\d+)\s*(d[ií]as|d[ií]a)',
            r'para\s+(\d+)\s*(d[ií]as|d[ií]a)',
            r'(\d+)\s*(d[ií]as|d[ií]a)\s+(?:seguidos|consecutivos)?'
        ]
        
        for pattern in duration_patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            # CORRECCIÓN: Verificar que match existe y tiene grupos
            if match and match.groups():
                cantidad = match.group(1)
                unidad = match.group(2) if len(match.groups()) > 1 else "días"
                info["duration"] = f"{cantidad} {unidad}"
                break
        
        # Si no se encontró duración, usar valor por defecto
        if not info["duration"] and info["action"] == "add_medication":
            info["duration"] = "7 días"
        
        # 8. Calcular confianza (MEJORADO)
        elementos_importantes = ["medication", "action"]
        elementos_secundarios = ["dosage", "frequency", "time", "duration"]
        
        encontrados_importantes = sum(1 for key in elementos_importantes if info[key])
        encontrados_secundarios = sum(1 for key in elementos_secundarios if info[key])
        
        # Fórmula de confianza mejorada
        base_conf = encontrados_importantes / len(elementos_importantes)
        extra_conf = encontrados_secundarios / len(elementos_secundarios) * 0.5
        info["confidence"] = min(1.0, base_conf + extra_conf)
        
        # Bonus por comando Dosis bien estructurado
        if info["is_dosis_command"] and info["action"] == "add_medication":
            info["confidence"] = min(1.0, info["confidence"] + 0.2)
        
        return info
    
    def _extract_medication_improved(self, text: str, action: Optional[str]) -> Optional[str]:
        """Extraer nombre de medicamento con lógica mejorada"""
        
        # Lista de medicamentos comunes en español
        common_medications = [
            'paracetamol', 'ibuprofeno', 'omeprazol', 'aspirina', 'amoxicilina',
            'loratadina', 'metformina', 'enalapril', 'atorvastatina', 'losartan',
            'clonazepam', 'diazepam', 'sertralina', 'citalopram', 'warfarin',
            'insulina', 'levotiroxina', 'metoprolol', 'hidroclorotiazida',
            'simvastatina', 'ramipril', 'valsartan', 'amlodipino', 'naproxeno',
            'ketorolaco', 'dexametasona', 'prednisona', 'salbutamol', 'ventolín'
        ]
        
        # 1. Buscar medicamentos comunes
        for med in common_medications:
            if med in text:
                return med.capitalize()
        
        # 2. Si tenemos spaCy, usarlo
        if self.nlp:
            doc = self.nlp(text)
            
            # Buscar sustantivos después de verbos de acción
            action_words = ['agregar', 'añadir', 'tomar', 'poner', 'programar', 
                          'agrégame', 'añádeme', 'ponme', 'programame']
            
            for i, token in enumerate(doc):
                if token.text in action_words and i + 1 < len(doc):
                    # Buscar sustantivo en las próximas 3 palabras
                    for j in range(i + 1, min(i + 4, len(doc))):
                        if doc[j].pos_ in ["NOUN", "PROPN"] and len(doc[j].text) > 3:
                            # Verificar que no sea palabra común
                            common_words = ['medicamento', 'pastilla', 'tableta', 
                                          'cápsula', 'jarabe', 'dosis', 'hora',
                                          'mañana', 'tarde', 'noche', 'día']
                            if doc[j].text.lower() not in common_words:
                                return doc[j].text.capitalize()
        
        # 3. Patrones regex de respaldo
        patterns = [
            r'(?:agregar|añadir|tomar|poner|programar|agrégame|añádeme|ponme|programame)\s+(?:el\s+)?(\w{3,})',
            r'medicamento\s+(?:de\s+)?(\w{3,})',
            r'pastilla\s+(?:de\s+)?(\w{3,})',
            r'cápsula\s+(?:de\s+)?(\w{3,})',
            r'\b(\w+ol)\b',  # Termina en "ol" como paracetamol, omeprazol
            r'\b(\w+ina)\b',  # Termina en "ina" como amoxicilina
            r'\b(\w+il)\b',   # Termina en "il" como enalapril
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            # CORRECCIÓN: Verificar match y grupos
            if match and match.groups():
                candidate = match.group(1).lower()
                # Filtrar palabras comunes
                if (len(candidate) > 3 and 
                    candidate not in ['medicamento', 'pastilla', 'tableta', 
                                    'cápsula', 'dosis', 'hora', 'día']):
                    return candidate.capitalize()
        
        return None
    
    def _regex_extraction(self, text):
        """Extracción básica con regex si spaCy no está disponible"""
        # Mantén tu versión actual como fallback
        info = {
            "medication": None,
            "dosage": None,
            "time": None,
            "frequency": None,
            "action": None,
            "duration": None,
            "confidence": 0.0,
            "is_dosis_command": False,
            "raw_text": text
        }
        
        text_lower = text.lower()
        
        # Detección básica de "Mi Dosis"
        if re.search(r"mi dosis|^dosis\b", text_lower):
            info["is_dosis_command"] = True
        
        # Extracción simple
        med_match = re.search(r"(?:medicina|medicamento|pastilla)\s+(\w+)", text_lower)
        # CORRECCIÓN: Verificar match y grupos
        if med_match and med_match.groups():
            info["medication"] = med_match.group(1).capitalize()
        
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