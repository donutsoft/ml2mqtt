from typing import Dict, Any, ClassVar
from .base import BasePreprocessor
from collections import defaultdict

class RollingAverage(BasePreprocessor):
    """Calculates rolling averages over a specified window size for each entity in the observations."""
    
    name: ClassVar[str] = "Rolling Average"
    type: ClassVar[str] = "rolling_average"
    description = "Calculates rolling averages over a specified window size for each entity in the observations."

    def __init__(self, dbId: int, **kwargs):
        super().__init__(dbId, **kwargs)
        self.windowSize = self.config['windowSize']

    def process(self, observation: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        result = observation.copy()

        if "rollingData" not in state:
            state["rollingData"] = {}
        rollingData = state["rollingData"]

        # Process each entity in the observation
        for entity, value in observation.items():
            if not self.canConsume(entity):
                continue

            value = result[entity]
            if not entity in rollingData:
                rollingData[entity] = [value]
            else:
                rollingData[entity].append(value)

            if len(rollingData[entity]) > self.windowSize and len(rollingData[entity]) > 0:
                rollingData[entity].pop(0)

            result[entity] = round(sum(rollingData[entity]) / len(rollingData[entity]), 4)

        return result
    
    def configToString(self) -> str:
        return f"I will calculate a rolling average over a window size of {self.windowSize} observations."