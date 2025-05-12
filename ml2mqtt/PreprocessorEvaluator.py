from preprocessors.base import BasePreprocessor
from typing import List

class PreprocessorEvaluator:
    def __init__(self, preprocessors: List[BasePreprocessor]):
        self.preprocessors = preprocessors
        pass

    def evaluate(self, input):
        result = []
        for processor in self.preprocessors:
            procResult = processor.to_dict()
            procResult['consumes'] = {sensor: value for sensor, value in input.items() if processor.canConsume(sensor)}
            procResult['produces'] = processor.process(input, {})
            input = procResult['produces']
            result.append(procResult)
        return result