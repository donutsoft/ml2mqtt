from typing import Dict, Any, ClassVar
from .base import BasePreprocessor
from collections import defaultdict

class TemporalExpander(BasePreprocessor):
    """Transforms a series of recent observations into distinct columns representing the current value and specified previous time steps."""
    
    name: ClassVar[str] = "Temporal Expander"
    type: ClassVar[str] = "temporal_expander"
    description = "Transforms a series of recent observations into distinct columns representing the current value and specified previous time steps."

    def __init__(self, dbId: int, **kwargs):
        super().__init__(dbId, **kwargs)
        self.lookback = self.config['lookback']
    
    def process(self, observation: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        result = observation.copy()

        if "previousObservations" not in state:
            state["previousObservations"] = {}
        previousObservations = state["previousObservations"]

        # Process either a single entity or all entities
        for entity in observation:
            if not self.canConsume(entity):
                continue

            value = result[entity]
            for i in range(0, self.lookback):
                if not entity in previousObservations:
                    previousObservations[entity] = []
                if i < len(previousObservations[entity]):
                    result[f"{entity}_{i}"] = previousObservations[entity][i]
                else:
                    result[f"{entity}_{i}"] = None

            previousObservations[entity].append(value)
            if len(previousObservations[entity]) > self.lookback:
                previousObservations[entity].pop(0)
        return result
    
    def configToString(self) -> str:
        return f"I will look back for {self.lookback} steps and add those fields as additional columns"