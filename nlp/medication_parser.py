import spacy
import re
from datetime import datetime, time
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class MedicationParser:
    def __init__(self):
        """Cargar modelo de spaCy para español"""
        try:
            # Cargar modelo de español
            self.nlp = spacy.load("es_core_news_sm")
            logger.info("✓ Modelo SpaCy cargado exitosamente")
        except Exception as e:
            logger.warning(f"Modelo spaCy no encontrado: {e}")
            self.nlp = None
        
        # Lista de medicamentos comunes en español
        self.common_medications = [
            "paracetamol", "ibuprofeno", "omeprazol", "aspirina", 
            "amoxicilina", "loratadina", "metformina", "enalapril",
            "atorvastatina", "losartán", "clonazepam", "diazepam",
            "sertralina", "citalopram", "warfarin", "insulina",
            "levotiroxina", "metoprolol", "hidroclorotiazida",
            "simvastatina", "ramipril", "valsartán", "amlodipino",
            "bisoprolol", "prednisona", "dexametasona"
        ]
        
        # Frecuencias comunes
        self.frequency_map = {
            "diario": "Diario",
            "todos los días": "Diario",
            "cada día": "Diario",
            "una vez al día": "Diario",
            "cada 8 horas": "Cada 8 horas",
            "cada ocho horas": "Cada 8 horas",
            "cada 12 horas": "Cada 12 horas",
            "cada doce horas": "Cada 12 horas",
            "dos veces al día": "Cada 12 horas",
            "semanal": "Semanal",
            "una vez por semana": "Semanal",
            "cada semana": "Semanal",
            "cuando sea necesario": "Cuando sea necesario",
            "al necesitar": "Cuando sea necesario"
        }
        
        # Acciones de voz
        self.action_keywords = {
            "agregar": "add_medication",
            "añadir": "add_medication",
            "poner": "add_medication",
            "programar": "add_medication",
            "registrar": "add_medication",
            "eliminar": "delete_medication",
            "quitar": "delete_medication",
            "borrar": "delete_medication",
            "cancelar": "delete_medication",
            "listar": "list_medications",
            "mostrar": "list_medications",
            "ver": "list_medications",
            "qué": "list_medications",
            "cuáles": "list_medications",
            "recordar": "set_reminder",
            "recordarme": "set_reminder",
            "avisar": "set_reminder",
            "alerta": "set_reminder",
            "tomé": "check_medication",
            "tomo": "check_medication",
            "tomar": "check_medication",
            "consumí": "check_medication",
            "hoy": "check_today",
            "mañana": "check_tomorrow",
            "ayer": "check_yesterday"
        }
    
    def extract_info(self, text: str) -> Dict[str, Any]:
        """Extraer información de medicamentos del texto con NLP mejorado"""
        text_lower = text.lower().strip()
        logger.info(f"Procesando texto: {text_lower}")
        
        info = {
            "action": None,
            "medication": None,
            "dosage": None,
            "frequency": None,
            "time": None,
            "quantity": None,
            "duration": None,
            "confidence": 1.0,
            "raw_text": text
        }
        
        # 1. Detectar acción
        info["action"] = self._detect_action(text_lower)
        
        # 2. Extraer medicamento
        info["medication"] = self._extract_medication(text_lower)
        
        # 3. Extraer dosis
        info["dosage"] = self._extract_dosage(text_lower)
        
        # 4. Extraer frecuencia
        info["frequency"] = self._extract_frequency(text_lower)
        
        # 5. Extraer hora
        info["time"] = self._extract_time(text_lower)
        
        # 6. Extraer cantidad
        info["quantity"] = self._extract_quantity(text_lower)
        
        # 7. Extraer duración
        info["duration"] = self._extract_duration(text_lower)
        
        # 8. Calcular confianza
        info["confidence"] = self._calculate_confidence(info)
        
        logger.info(f"Información extraída: {info}")
        return info
    
    def _detect_action(self, text: str) -> Optional[str]:
        """Detectar acción solicitada usando NLP"""
        if self.nlp:
            doc = self.nlp(text)
            
            # Buscar verbos de acción
            for token in doc:
                if token.lemma_ in self.action_keywords:
                    return self.action_keywords[token.lemma_]
        
        # Fallback a regex
        for keyword, action in self.action_keywords.items():
            if keyword in text:
                return action
        
        return None
    
    def _extract_medication(self, text: str) -> Optional[str]:
        """Extraer nombre del medicamento usando NLP"""
        # Buscar medicamentos comunes
        for med in self.common_medications:
            if med in text:
                return med.capitalize()
        
        if self.nlp:
            doc = self.nlp(text)
            
            # Buscar sustantivos que podrían ser medicamentos
            for ent in doc.ents:
                if ent.label_ in ["MISC", "ORG", "PRODUCT"]:
                    # Verificar si parece un medicamento
                    if len(ent.text) > 3 and any(c.isdigit() for c in ent.text):
                        continue  # Probablemente una dosis
                    return ent.text.capitalize()
            
            # Buscar sustantivos compuestos
            for token in doc:
                if token.pos_ == "NOUN" and len(token.text) > 3:
                    # Verificar patrón común de medicamentos
                    if token.text.lower() not in ["medicamento", "pastilla", "tableta", "cápsula"]:
                        return token.text.capitalize()
        
        # Regex fallback
        patterns = [
            r"medicamento\s+(\w+)",
            r"pastilla\s+(?:de\s+)?(\w+)",
            r"tomar\s+(\w+)",
            r"(\w+)\s+(?:mg|g|ml|cápsula|pastilla|comprimido)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).capitalize()
        
        return None
    
    def _extract_dosage(self, text: str) -> Optional[str]:
        """Extraer dosis con mejor precisión"""
        patterns = [
            r"(\d+)\s*(mg|g|ml|mcg|µg|ui|iu|unidades)",
            r"(\d+)\s*(comprimidos?|pastillas?|cápsulas?|tabletas?|píldoras?)",
            r"(\d+)\s*(mg|g|ml)\s*de\s*\w+",
            r"dosis\s+de\s+(\d+)\s*(mg|g|ml)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                unit = match.group(2).lower()
                if unit in ["comprimidos", "pastillas", "cápsulas", "tabletas", "píldoras"]:
                    return f"{match.group(1)} {unit}"
                else:
                    return f"{match.group(1)}{unit}"
        
        return None
    
    def _extract_frequency(self, text: str) -> str:
        """Extraer frecuencia"""
        for keyword, frequency in self.frequency_map.items():
            if keyword in text:
                return frequency
        
        # Detección por contexto
        if "cada" in text and "hora" in text:
            match = re.search(r"cada\s+(\d+)\s+horas?", text)
            if match:
                hours = int(match.group(1))
                if hours == 8:
                    return "Cada 8 horas"
                elif hours == 12:
                    return "Cada 12 horas"
                elif hours == 24 or hours == 1:
                    return "Diario"
        
        return "Diario"  # Valor por defecto
    
    def _extract_time(self, text: str) -> Optional[str]:
        """Extraer hora con mejor manejo de formatos"""
        # Formato 24h: 14:30, 8:00
        time_pattern_24h = r"(\d{1,2}):(\d{2})"
        match = re.search(time_pattern_24h, text)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            if 0 <= hour < 24 and 0 <= minute < 60:
                return f"{hour:02d}:{minute:02d}"
        
        # Formato con am/pm
        time_pattern_ampm = r"(\d{1,2})\s*(?:\.|:)?\s*(\d{2})?\s*(am|pm|a\.m\.|p\.m\.|de la mañana|de la tarde|de la noche)"
        match = re.search(time_pattern_ampm, text, re.IGNORECASE)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2) or "0")
            period = match.group(3).lower()
            
            # Convertir a 24h
            if "pm" in period or "tarde" in period or "noche" in period:
                if hour < 12:
                    hour += 12
            elif "am" in period or "mañana" in period:
                if hour == 12:
                    hour = 0
            
            return f"{hour:02d}:{minute:02d}"
        
        # Horas simples
        hour_pattern = r"(\d{1,2})\s+horas?"
        match = re.search(hour_pattern, text)
        if match:
            hour = int(match.group(1))
            if 0 <= hour < 24:
                return f"{hour:02d}:00"
        
        # Expresiones comunes
        time_expressions = {
            "mediodía": "12:00",
            "medio día": "12:00",
            "medianoche": "00:00",
            "media noche": "00:00",
            "en la mañana": "08:00",
            "por la mañana": "08:00",
            "en la tarde": "14:00",
            "por la tarde": "14:00",
            "en la noche": "20:00",
            "por la noche": "20:00",
            "al despertar": "07:00",
            "después de desayunar": "08:30",
            "después de almorzar": "14:00",
            "después de comer": "14:00",
            "después de cenar": "20:00",
            "antes de dormir": "22:00"
        }
        
        for expr, time_str in time_expressions.items():
            if expr in text:
                return time_str
        
        return None
    
    def _extract_quantity(self, text: str) -> Optional[str]:
        """Extraer cantidad total"""
        patterns = [
            r"(\d+)\s*(caja|cajas|blister|blisters|frascos?|botellas?)",
            r"(\d+)\s*(unidades|uds|u)",
            r"para\s+(\d+)\s+(días|semanas|meses)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return f"{match.group(1)} {match.group(2)}"
        
        return None
    
    def _extract_duration(self, text: str) -> Optional[str]:
        """Extraer duración del tratamiento"""
        patterns = [
            r"por\s+(\d+)\s*(días|semanas|meses)",
            r"durante\s+(\d+)\s*(días|semanas|meses)",
            r"(\d+)\s*(días|semanas|meses)\s+de\s+tratamiento",
            r"hasta\s+el\s+(\d{1,2}/\d{1,2}/\d{4})"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                if len(match.groups()) > 1:
                    return f"{match.group(1)} {match.group(2)}"
                else:
                    return match.group(1)
        
        return None
    
    def _calculate_confidence(self, info: Dict[str, Any]) -> float:
        """Calcular confianza de la extracción"""
        confidence = 1.0
        
        # Penalizar si falta información crítica
        if info["action"] is None:
            confidence *= 0.7
        
        if info["action"] == "add_medication" and info["medication"] is None:
            confidence *= 0.6
        
        if info["action"] == "add_medication" and info["dosage"] is None:
            confidence *= 0.8
        
        # Premiar si tenemos buena información
        if info["medication"] and info["dosage"]:
            confidence *= 1.2
        
        if info["time"]:
            confidence *= 1.1
        
        # Limitar entre 0 y 1
        return max(0.0, min(1.0, confidence))
    
    def validate_medication_info(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """Validar y completar información de medicamento"""
        validated = info.copy()
        
        # Validar formato de hora
        if validated.get("time"):
            try:
                hour, minute = map(int, validated["time"].split(":"))
                if not (0 <= hour < 24 and 0 <= minute < 60):
                    validated["time"] = None
            except:
                validated["time"] = None
        
        # Validar dosis
        if validated.get("dosage"):
            # Remover espacios innecesarios
            validated["dosage"] = validated["dosage"].replace(" ", "")
        
        return validated
    
    def format_for_display(self, info: Dict[str, Any]) -> str:
        """Formatear información para mostrar al usuario"""
        parts = []
        
        if info.get("action"):
            action_map = {
                "add_medication": "Agregar",
                "delete_medication": "Eliminar",
                "list_medications": "Listar",
                "set_reminder": "Recordatorio para",
                "check_medication": "Verificar",
                "check_today": "Hoy necesitas"
            }
            parts.append(action_map.get(info["action"], info["action"]))
        
        if info.get("medication"):
            parts.append(info["medication"])
        
        if info.get("dosage"):
            parts.append(f"({info['dosage']})")
        
        if info.get("frequency"):
            parts.append(f"con frecuencia {info['frequency']}")
        
        if info.get("time"):
            parts.append(f"a las {info['time']}")
        
        return " ".join(parts)

# Instancia global
parser = MedicationParser()

def extract_medication_info(text: str) -> Dict[str, Any]:
    """Función para usar desde otros módulos"""
    try:
        result = parser.extract_info(text)
        validated = parser.validate_medication_info(result)
        return validated
    except Exception as e:
        logger.error(f"Error extrayendo información de medicamento: {e}")
        return {
            "action": None,
            "medication": None,
            "dosage": None,
            "frequency": None,
            "time": None,
            "confidence": 0.0,
            "error": str(e)
        }

def format_medication_response(info: Dict[str, Any]) -> str:
    """Formatear respuesta para voz"""
    return parser.format_for_display(info)

# Prueba de la funcionalidad
if __name__ == "__main__":
    test_cases = [
        "Agregar paracetamol 500mg cada 8 horas a las 14:30",
        "Recuérdame tomar omeprazol por la mañana",
        "¿Qué medicamentos tengo programados para hoy?",
        "Eliminar ibuprofeno de mis recordatorios",
        "Tomar amoxicilina 250mg después del almuerzo",
        "Programar enalapril 10mg una vez al día"
    ]
    
    for test in test_cases:
        print(f"\nTest: {test}")
        result = extract_medication_info(test)
        print(f"Resultado: {result}")
        print(f"Formateado: {format_medication_response(result)}")