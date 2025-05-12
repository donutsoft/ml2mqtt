from typing import Dict, Any, Optional, ClassVar
from ModelStore import ModelStore
from .base import BasePreprocessor

class NullHandler(BasePreprocessor):
    """Replaces None values with default values from ModelStore."""
    
    name: ClassVar[str] = "Null Handler"
    type: ClassVar[str] = "null_handler"
    description: ClassVar[str] = "Replaces None values with predefined value suitable for an ML model."
        
    def __init__(self, dbId: int, **kwargs):
        super().__init__(dbId, **kwargs)
    
    def process(self, observation: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        result = observation.copy()
        
        for entity in result:
            if not self.canConsume(entity):
                continue

            value = result[entity]
            if value is None:
                if self.config['replacementType'] == 'float':
                    result[entity] = float(self.config['nullReplacement'])
                else:
                    result[entity] = self.config['nullReplacement']

        return result 
    
    def configToString(self) -> str:
        if self.config['replacementType'] == 'float':
            return "I will change values of None to " + self.config['nullReplacement']
        else:
            return "I will change values of None to '" + self.config['nullReplacement'] + "'"