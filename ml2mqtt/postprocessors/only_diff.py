from typing import Dict, Any, Optional, Tuple, ClassVar
from .base import BasePostprocessor
import logging

class OnlyDiffPostprocessor(BasePostprocessor):
    """Postprocessor that drops results unless they differ from the previous result."""
    
    type: ClassVar[str] = "only_diff"
    description: ClassVar[str] = "Drops results unless they differ from the previous result"
    
    config_schema: ClassVar[Dict[str, Any]] = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }
    
    def __init__(self, **kwargs):
        """
        Initialize the only diff postprocessor.
        
        Args:
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.last_label = None
        self.logger = logging.getLogger(__file__)
    
    def process(self, observation: Dict[str, Any], label: Any) -> Tuple[Dict[str, Any], Optional[Any]]:
        """
        Process the observation and label, dropping if same as previous.
        
        Args:
            observation: Dictionary of entity values
            label: The predicted label
            
        Returns:
            Tuple of (observation, label or None if same as previous)
        """
        if label == self.last_label:
            return observation, None
        
        self.last_label = label
        return observation, label 
    
    def configToString(self) -> str:
        return ""