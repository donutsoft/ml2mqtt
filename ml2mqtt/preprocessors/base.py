from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, ClassVar

class BasePreprocessor(ABC):
    """Base class for all preprocessors."""
    
    # Static metadata that must be defined by subclasses
    name: ClassVar[str] = "name"
    type: ClassVar[str] = "type"
    description: ClassVar[str] = "Base preprocessor"  # Human-readable description
    
    # Static configuration schema that must be defined by subclasses
    config_schema: ClassVar[Dict[str, Any]] = {
        "type": "object",
        "properties": {
            "entity": {
                "type": "string",
                "description": "Target entity to process (empty for all entities)"
            }
        }
    }
    
    def __init__(self, dbId: int, **kwargs):
        """
        Initialize the preprocessor.
        
        Args:
            entity: Optional entity name to process. If None, processes all entities.
            **kwargs: Additional configuration parameters
        """
        self.dbId = dbId
        self.config = kwargs
    
    @abstractmethod
    def process(self, observation: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the observation.
        
        Args:
            observation: Dictionary of entity values
            
        Returns:
            Modified observation dictionary
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert preprocessor configuration to dictionary.
        """
        return {
            "name": self.name,
            "type": self.type,
            "dbId": self.dbId,
            "config": self.config,
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BasePreprocessor':
        """
        Create preprocessor instance from dictionary.
        """
        return cls(
            entity=data.get("entity"),
            **data.get("config", {})
        ) 