from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BasePreprocessor(ABC):
    """Base class for all preprocessors."""
    
    name: str = "base"  # Override this in subclasses
    description: str = "Base preprocessor"  # Override this in subclasses
    template_name: str = "base_config.html"  # Override this in subclasses
    
    def __init__(self, entity: Optional[str] = None, **kwargs):
        """
        Initialize the preprocessor.
        
        Args:
            entity: Optional entity name to process. If None, processes all entities.
            **kwargs: Additional configuration parameters
        """
        self.entity = entity
        self.config = kwargs
    
    @abstractmethod
    def process(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the observation.
        
        Args:
            observation: Dictionary of entity values
            
        Returns:
            Modified observation dictionary
        """
        pass
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """
        Return JSON schema for this preprocessor's configuration.
        Override this in subclasses to provide custom configuration schema.
        """
        return {
            "type": "object",
            "properties": {
                "entity": {
                    "type": "string",
                    "description": "Target entity to process (empty for all entities)"
                }
            }
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert preprocessor configuration to dictionary.
        """
        return {
            "type": self.name,
            "entity": self.entity,
            "config": self.config
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