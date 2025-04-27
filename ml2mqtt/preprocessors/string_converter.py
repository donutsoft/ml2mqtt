from typing import Dict, Any, Optional
from .base import BasePreprocessor

class StringConverterPreprocessor(BasePreprocessor):
    """Converts string values to floats and handles unknown values."""
    
    name = "string_converter"
    description = "Converts string values to floats and replaces 'unknown'/'unavailable' with None"
    
    def __init__(self, entity: Optional[str] = None, **kwargs):
        super().__init__(entity, **kwargs)
        self.unknown_values = {"unknown", "unavailable", "none", "null"}
    
    def process(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        result = observation.copy()
        
        # Process either a single entity or all entities
        entities_to_process = [self.entity] if self.entity else result.keys()
        
        for entity in entities_to_process:
            if entity not in result:
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
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "entity": {
                    "type": "string",
                    "description": "Target entity to process (empty for all entities)"
                }
            }
        } 