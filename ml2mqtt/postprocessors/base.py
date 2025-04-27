from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple

class BasePostprocessor(ABC):
    """Base class for all postprocessors."""
    
    name: str = "base"  # Override this in subclasses
    description: str = "Base postprocessor"  # Override this in subclasses
    template_name: str = "base_config.html"  # Override this in subclasses
    
    def __init__(self, **kwargs):
        """
        Initialize the postprocessor.
        
        Args:
            **kwargs: Additional configuration parameters
        """
        self.config = kwargs
    
    @abstractmethod
    def process(self, observation: Dict[str, Any], label: Any) -> Tuple[Dict[str, Any], Optional[Any]]:
        """
        Process the observation and label.
        
        Args:
            observation: Dictionary of entity values
            label: The predicted label
            
        Returns:
            Tuple of (modified observation dictionary, modified label or None if should be dropped)
        """
        pass
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """
        Return JSON schema for this postprocessor's configuration.
        Override this in subclasses to provide custom configuration schema.
        """
        return {
            "type": "object",
            "properties": {}
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert postprocessor configuration to dictionary.
        """
        return {
            "type": self.name,
            "config": self.config
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BasePostprocessor':
        """
        Create postprocessor instance from dictionary.
        """
        return cls(**data.get("config", {})) 