from typing import Dict, Any, Optional, ClassVar
from ModelStore import ModelStore
from .base import BasePreprocessor

class DefaultValuePreprocessor(BasePreprocessor):
    """Replaces None values with default values from ModelStore."""
    
    type: ClassVar[str] = "default_value"
    description: ClassVar[str] = "Replaces None values with default values from ModelStore"
    
    config_schema: ClassVar[Dict[str, Any]] = {
        "type": "object",
        "properties": {
            "entity": {
                "type": "string",
                "description": "Target entity to process (empty for all entities)"
            }
        }
    }
    
    def __init__(self, entity: Optional[str] = None, **kwargs):
        super().__init__(entity, **kwargs)
        self.model_store = ModelStore()
    
    def process(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        result = observation.copy()
        
        # Process either a single entity or all entities
        entities_to_process = [self.entity] if self.entity else result.keys()
        
        for entity in entities_to_process:
            if entity not in result:
                continue
                
            value = result[entity]
            
            # Replace None with default value if available
            if value is None:
                default_value = self.model_store.get_default_value(entity)
                if default_value is not None:
                    result[entity] = default_value
        
        return result 