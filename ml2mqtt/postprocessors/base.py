from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple, ClassVar

class BasePostprocessor(ABC):
    """Base class for all postprocessors."""
    
    # Static metadata that must be defined by subclasses
    id: ClassVar[str] = "base"  # Unique identifier for the postprocessor
    description: ClassVar[str] = "Base postprocessor"  # Human-readable description
    
    # Static configuration schema that must be defined by subclasses
    config_schema: ClassVar[Dict[str, Any]] = {
        "type": "object",
        "properties": {}
    }
    
    def __init__(self, dbId: int, **kwargs):
        """
        Initialize the postprocessor.
        
        Args:
            dbId: Database ID for this postprocessor
            **kwargs: Additional configuration parameters
        """
        self.dbId = dbId
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
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert postprocessor configuration to dictionary.
        """
        return {
            "type": self.id,
            "config": self.config
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BasePostprocessor':
        """
        Create postprocessor instance from dictionary.
        """
        return cls(**data.get("config", {})) 