from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, ClassVar
import logging

class BasePreprocessor(ABC):
    """Base class for all preprocessors."""
    
    # Static metadata that must be defined by subclasses
    name: ClassVar[str] = "name"
    type: ClassVar[str] = "type"
    description: ClassVar[str] = "Base preprocessor"  # Human-readable description
    logger = logging.getLogger(__name__)
    sensors = []

    def __init__(self, dbId: int, **kwargs):
        """
        Initialize the preprocessor.
        
        Args:
            entity: Optional entity name to process. If None, processes all entities.
            **kwargs: Additional configuration parameters
        """
        self.dbId = dbId
        self.config = kwargs
        self.sensors = set([key for item in self.config['sensor'] for key, value in item.items() if value is True])
    
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
            "config_string": self.configToString(),
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
    
    def canConsume(self, sensorKey: str) -> bool:
        return "SELECT_ALL" in self.sensors or sensorKey in self.sensors
    
    @abstractmethod
    def configToString(self) -> str:
        return ""