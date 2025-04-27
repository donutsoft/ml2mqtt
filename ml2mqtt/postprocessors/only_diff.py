from typing import Dict, Any, Optional, Tuple
from .base import BasePostprocessor

class OnlyDiffPostprocessor(BasePostprocessor):
    """Postprocessor that drops results unless they differ from the previous result."""
    
    name = "only_diff"
    description = "Drops results unless they differ from the previous result"
    
    def __init__(self, **kwargs):
        """
        Initialize the only diff postprocessor.
        
        Args:
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.last_label = None
    
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
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {}
        } 