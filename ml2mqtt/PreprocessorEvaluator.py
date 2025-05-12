from preprocessors.base import BasePreprocessor
from typing import List
from collections import defaultdict

class PreprocessorEvaluator:
    def __init__(self, preprocessors: List[BasePreprocessor]):
        self.preprocessors = preprocessors

    def evaluate(self, observations):
        
        result = []
        dataStore = defaultdict(dict)

        if len(observations) == 0:
            observations.append({})

        for idx, input in enumerate(observations):
            proposedResult = []
            for processor in self.preprocessors:
                procResult = processor.to_dict()
                procResult['consumes'] = {sensor: value for sensor, value in input.items() if processor.canConsume(sensor)}
                procResult['produces'] = processor.process(input, dataStore[processor])
                input = procResult['produces']
                proposedResult.append(procResult)

            # Only append to result for the last input
            if idx == len(observations) - 1:
                result.extend(proposedResult)

        return result