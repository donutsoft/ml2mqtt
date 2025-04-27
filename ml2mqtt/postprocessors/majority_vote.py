from collections import deque
from typing import Dict, Any, Optional, Tuple, ClassVar
from .base import BasePostprocessor

class MajorityVotePostprocessor(BasePostprocessor):
    """Postprocessor that waits for N results and returns the most common label."""
    
    id: ClassVar[str] = "majority_vote"
    description: ClassVar[str] = "Waits for N results and returns the most common label"
    
    config_schema: ClassVar[Dict[str, Any]] = {
        "type": "object",
        "properties": {
            "window_size": {
                "type": "integer",
                "description": "Number of results to consider for majority voting",
                "minimum": 1
            }
        },
        "required": ["window_size"]
    }
    
    def __init__(self, window_size: int = 5, **kwargs):
        """
        Initialize the majority vote postprocessor.
        
        Args:
            window_size: Number of results to consider for majority voting
            **kwargs: Additional configuration parameters
        """
        super().__init__(**kwargs)
        self.window_size = window_size
        self.window = deque(maxlen=window_size)
    
    def process(self, observation: Dict[str, Any], label: Any) -> Tuple[Dict[str, Any], Optional[Any]]:
        """
        Process the observation and label using majority voting.
        
        Args:
            observation: Dictionary of entity values
            label: The predicted label
            
        Returns:
            Tuple of (observation, majority label or None if window not full)
        """
        self.window.append(label)
        
        # If window is not full yet, drop the result
        if len(self.window) < self.window_size:
            return observation, None
            
        # Count occurrences of each label
        label_counts = {}
        for l in self.window:
            label_counts[l] = label_counts.get(l, 0) + 1
            
        # Find the most common label
        majority_label = max(label_counts.items(), key=lambda x: x[1])[0]
        
        return observation, majority_label 