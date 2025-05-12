from typing import Dict, Any, Optional, ClassVar
from .base import BasePreprocessor

class TypeCaster(BasePreprocessor):
    """Converts string values to floats and handles unknown values."""
    
    name: ClassVar[str] = "Type Caster"
    type: ClassVar[str] = "type_caster"
    description = "Converts string values to floats and replaces 'unknown' and 'unavailable' with None"
    
    def __init__(self, dbId: int, **kwargs):
        super().__init__(dbId, **kwargs)
        self.unknown_values = {"unknown", "unavailable", "none", "null"}
    
    def process(self, observation: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        result = observation.copy()
        
        # Process either a single entity or all entities
        #entities_to_process = [self.entity] if self.entity else result.keys()        
        for entity in result:
            if not self.canConsume(entity):
                continue

            value = result[entity]            
            # Handle string values
            if isinstance(value, str):
                # Check for unknown values
                if value.lower() in self.unknown_values:
                    result[entity] = None
                else:
                    # Try to convert to float
                    try:
                        result[entity] = float(value)
                    except ValueError:
                        # Keep original value if conversion fails
                        pass
        
        return result
    
    def configToString(self) -> str:
        return ""