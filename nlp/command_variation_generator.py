"""
Generador de variaciones de comandos para entrenar el asistente 'Mi Dosis'
"""
import spacy
import re
from datetime import datetime

class CommandVariationGenerator:
    """Genera variaciones de comandos para entrenar el asistente"""
    
    def __init__(self):
        self.templates = [
            # TEMPLATE: {starter} {action} {medication} {dosage} {time} {frequency} {duration}
            "{starter} {action} {medication} de {dosage} {time} con frecuencia {frequency} {duration}",
            "{starter} {action} {medication} {dosage} {time} cada {frequency} {duration}",
            "{starter} {action} {dosage} de {medication} {time} tomando {frequency} {duration}",
            "{starter} {action} el {medication} de {dosage} {time} {frequency} {duration}",
            "{starter} {action} {medication} con dosis de {dosage} {time} {frequency} por {duration}",
            "{starter} {action} tomar {medication} {dosage} {time} {frequency} {duration}",
            "{starter} por favor {action} {medication} {dosage} {time} {frequency} {duration}",
            "{starter} quiero {action} {medication} {dosage} {time} {frequency} {duration}",
            "{starter} necesito {action} {medication} {dosage} {time} {frequency} {duration}"
        ]
        
    def generate_variations(self, base_command: str) -> List[str]:
        """
        Generar múltiples variaciones de un comando base
        
        Ejemplo:
        Input: "Mi Dosis agregame paracetamol de 500 mg a las 8 de la mañana..."
        Output: Lista de 50+ variaciones
        """
        variations = []
        
        # Componentes del comando base
        components = self._parse_base_command(base_command)
        
        if not components:
            return variations
        
        # Generar variaciones para cada componente
        starter_variations = self._get_starter_variations()
        action_variations = self._get_action_variations(components.get("action", ""))
        medication_variations = self._get_medication_variations(components.get("medication", ""))
        dosage_variations = self._get_dosage_variations(components.get("dosage", ""))
        time_variations = self._get_time_variations(components.get("time", ""))
        frequency_variations = self._get_frequency_variations(components.get("frequency", ""))
        duration_variations = self._get_duration_variations(components.get("duration", ""))
        
        # Combinar variaciones (limitar combinaciones)
        max_variations = 50
        variation_count = 0
        
        for template in self.templates[:3]:  # Usar solo 3 templates para no generar demasiadas
            for starter in starter_variations[:3]:
                for action in action_variations[:3]:
                    for medication in medication_variations[:2]:
                        for dosage in dosage_variations[:2]:
                            for time in time_variations[:2]:
                                for frequency in frequency_variations[:2]:
                                    for duration in duration_variations[:2]:
                                        if variation_count >= max_variations:
                                            break
                                            
                                        variation = template.format(
                                            starter=starter,
                                            action=action,
                                            medication=medication,
                                            dosage=dosage,
                                            time=time,
                                            frequency=frequency,
                                            duration=duration
                                        )
                                        variations.append(variation)
                                        variation_count += 1
        
        return variations
    
    def _parse_base_command(self, command: str) -> Dict[str, str]:
        """Parsear comando base para extraer componentes"""
        components = {}
        
        # Extraer starter
        starters = self._get_starter_variations()
        for starter in starters:
            if command.lower().startswith(starter.lower()):
                components["starter"] = starter
                break
        
        # Extraer acción
        action_patterns = [
            r'(?:agregar|añadir|poner|programar|registrar|necesitar|querer)',
            r'agrégame|añádeme|ponme|programame|registrame'
        ]
        
        for pattern in action_patterns:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                components["action"] = match.group(0)
                break
        
        # Extraer medicamento (simplificado)
        med_pattern = r'(?:agregar|añadir|poner|tomar)\s+(?:el\s+)?(\w+)'
        match = re.search(med_pattern, command, re.IGNORECASE)
        if match:
            components["medication"] = match.group(1)
        
        # Extraer dosis
        dosage_pattern = r'(\d+)\s*(mg|g|ml|tableta)'
        match = re.search(dosage_pattern, command, re.IGNORECASE)
        if match:
            components["dosage"] = f"{match.group(1)} {match.group(2)}"
        
        # Extraer hora
        time_pattern = r'a las (\d{1,2})(?::\d{2})?\s*(?:de la\s+)?(mañana|tarde|noche|am|pm)?'
        match = re.search(time_pattern, command, re.IGNORECASE)
        if match:
            hour = match.group(1)
            period = match.group(2) or ""
            components["time"] = f"a las {hour}{' ' + period if period else ''}"
        
        # Extraer frecuencia
        freq_pattern = r'cada\s+(\d+\s*(?:horas|días))'
        match = re.search(freq_pattern, command, re.IGNORECASE)
        if match:
            components["frequency"] = f"cada {match.group(1)}"
        
        # Extraer duración
        duration_pattern = r'por\s+(\d+\s*(?:días|semanas|meses))'
        match = re.search(duration_pattern, command, re.IGNORECASE)
        if match:
            components["duration"] = f"por {match.group(1)}"
        
        return components
    
    def _get_starter_variations(self) -> List[str]:
        return [
            "Mi Dosis", "Dosis", "Asistente", "Hey Dosis", "Hola Dosis",
            "OK Dosis", "Oye Dosis", "Asistente médico", "Asistente de medicamentos",
            "Medicación", "Recuérdame", "Por favor"
        ]
    
    def _get_action_variations(self, base_action: str) -> List[str]:
        action_map = {
            "agregar": [
                "agrégame", "añádeme", "ponme", "programame", "registrame",
                "creame", "iníciame", "comiénzame", "empézame", "necesito agregar",
                "quiero agregar", "requiero agregar", "preciso agregar", "deseo agregar",
                "recétame", "prescríbeme", "indícame", "configurame", "estableceme"
            ],
            "añadir": [
                "añádeme", "agrégame", "suma", "incluye", "incorpora",
                "agrega", "añade", "pon", "agregar", "poner"
            ]
        }
        
        # Buscar acción base en el mapa
        for action_key, variations in action_map.items():
            if action_key in base_action.lower():
                return variations
        
        # Si no se encuentra, devolver la acción base y algunas comunes
        return [base_action, "agrégame", "añádeme", "ponme"]
    
    def _get_medication_variations(self, base_med: str) -> List[str]:
        # Mapeo de medicamentos comunes y sus variaciones
        med_variations = {
            "paracetamol": [
                "paracetamol", "acetaminofén", "tylenol", "dolofin", "panadol",
                "el paracetamol", "paracetamol de 500", "paracetamol genérico"
            ],
            "ibuprofeno": [
                "ibuprofeno", "advil", "motrin", "ibu", "ibuprofeno de 400",
                "el ibuprofeno", "ibuprofeno genérico"
            ],
            "omeprazol": [
                "omeprazol", "prilosec", "losec", "omez", "omeprazol de 20",
                "el omeprazol", "cápsula de omeprazol"
            ],
            "aspirina": [
                "aspirina", "ácido acetilsalicílico", "aspirina de 100",
                "la aspirina", "aspirina infantil"
            ],
            "amoxicilina": [
                "amoxicilina", "amoxicilina de 500", "antibiótico",
                "la amoxicilina", "amoxicilina cápsulas"
            ]
        }
        
        # Buscar medicamento base
        base_lower = base_med.lower()
        for med_key, variations in med_variations.items():
            if med_key in base_lower:
                return variations
        
        # Si no se encuentra, devolver el medicamento base
        return [base_med]
    
    def _get_dosage_variations(self, base_dosage: str) -> List[str]:
        # "500 mg" -> variaciones
        match = re.match(r'(\d+)\s*(mg|g|ml|tableta|tabletas|cápsula|cápsulas)', base_dosage, re.IGNORECASE)
        if match:
            value, unit = match.groups()
            return [
                f"{value} {unit}",
                f"de {value} {unit}",
                f"dosis de {value} {unit}",
                f"{value}{unit}",
                f"{value} miligramos" if unit.lower() == "mg" else base_dosage,
            ]
        return [base_dosage]
    
    def _get_time_variations(self, base_time: str) -> List[str]:
        # Extraer hora y período
        match = re.search(r'a las (\d{1,2})(?:\s*(?:de la\s+)?(mañana|tarde|noche|am|pm))?', base_time, re.IGNORECASE)
        
        if not match:
            return [base_time]
        
        hour = match.group(1)
        period = match.group(2) or ""
        
        time_variations = []
        
        # Con período
        if period:
            period_lower = period.lower()
            if "mañana" in period_lower or "am" in period_lower:
                time_variations.extend([
                    f"a las {hour} de la mañana",
                    f"a las {hour} am",
                    f"en la mañana a las {hour}",
                    f"por la mañana a las {hour}",
                    f"a las {hour} en la mañana"
                ])
            elif "tarde" in period_lower:
                time_variations.extend([
                    f"a las {hour} de la tarde",
                    f"a las {hour} pm",
                    f"en la tarde a las {hour}",
                    f"por la tarde a las {hour}",
                    f"a las {hour} en la tarde"
                ])
            elif "noche" in period_lower or "pm" in period_lower:
                time_variations.extend([
                    f"a las {hour} de la noche",
                    f"a las {hour} pm",
                    f"en la noche a las {hour}",
                    f"por la noche a las {hour}",
                    f"a las {hour} en la noche"
                ])
        
        # Sin período específico
        time_variations.extend([
            f"a las {hour}",
            f"a las {hour}:00",
            f"a la hora {hour}",
            f"a las {hour} horas"
        ])
        
        return list(set(time_variations))  # Remover duplicados
    
    def _get_frequency_variations(self, base_freq: str) -> List[str]:
        # Extraer valor y unidad
        match = re.search(r'cada\s+(\d+)\s*(horas|días)', base_freq, re.IGNORECASE)
        
        if not match:
            return [base_freq]
        
        value = match.group(1)
        unit = match.group(2).lower()
        
        freq_variations = []
        
        if "hora" in unit:
            if value == "8":
                freq_variations.extend([
                    "cada 8 horas",
                    "cada ocho horas",
                    "tres veces al día",
                    "cada 8 hrs",
                    "cada ocho hrs",
                    "cada 8h"
                ])
            elif value == "12":
                freq_variations.extend([
                    "cada 12 horas",
                    "cada doce horas",
                    "dos veces al día",
                    "cada 12 hrs",
                    "cada doce hrs",
                    "cada 12h"
                ])
            elif value == "24":
                freq_variations.extend([
                    "cada 24 horas",
                    "diario",
                    "una vez al día",
                    "todos los días",
                    "cada día"
                ])
        elif "día" in unit:
            if value == "1":
                freq_variations.extend([
                    "diario",
                    "todos los días",
                    "una vez al día",
                    "cada día",
                    "diariamente"
                ])
            elif value == "7":
                freq_variations.extend([
                    "semanal",
                    "una vez por semana",
                    "cada semana",
                    "semanalmente"
                ])
        
        return list(set(freq_variations)) if freq_variations else [base_freq]
    
    def _get_duration_variations(self, base_duration: str) -> List[str]:
        # "14 días" -> variaciones
        match = re.match(r'por\s+(\d+)\s*(días|día|semanas|semana|meses|mes)', base_duration, re.IGNORECASE)
        
        if match:
            value, unit = match.groups()
            unit_singular = unit.rstrip('s') if unit.endswith('s') else unit
            
            variations = [
                f"por {value} {unit}",
                f"durante {value} {unit}",
                f"para {value} {unit}",
                f"por un período de {value} {unit}",
                f"por {value} {unit} seguidos",
            ]
            
            # Añadir variaciones con unidad en singular/plural
            if unit.endswith('s'):
                variations.append(f"por {value} {unit_singular}")
            else:
                variations.append(f"por {value} {unit}s")
            
            return variations
        
        return [base_duration]

# Función principal para probar el generador
def main():
    generator = CommandVariationGenerator()
    
    # Comando base de ejemplo
    base_command = "Mi Dosis agregame paracetamol de 500 mg a las 8 de la mañana con frecuencia cada 12 horas por 14 días"
    
    print("=" * 80)
    print("GENERADOR DE VARIACIONES PARA 'MI DOSIS'")
    print("=" * 80)
    
    print(f"\n📝 Comando base: {base_command}")
    
    # Parsear componentes
    components = generator._parse_base_command(base_command)
    print(f"\n🧩 Componentes extraídos: {components}")
    
    # Generar variaciones
    variations = generator.generate_variations(base_command)
    
    print(f"\n🔄 Variaciones generadas ({len(variations)}):")
    print("-" * 80)
    
    for i, variation in enumerate(variations[:10], 1):  # Mostrar solo primeras 10
        print(f"{i:2d}. {variation}")
    
    if len(variations) > 10:
        print(f"... y {len(variations) - 10} más")
    
    print("\n" + "=" * 80)
    print("🎯 Estas variaciones pueden usarse para entrenar el reconocedor de voz")
    print("y mejorar la comprensión del asistente 'Mi Dosis'")
    print("=" * 80)

if __name__ == "__main__":
    main()