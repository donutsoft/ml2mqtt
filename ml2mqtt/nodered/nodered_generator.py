from .nodered_types import HomeAssistantSelector, JoinNode, MqttOutputNode, HomeAssistantSensor, MqttInputNode
import json
#from ModelService import ModelService

class NodeRedGenerator:
    def __init__(self, modelService):
        self.modelService = modelService

    def generate(self):
        mqttOutput = MqttOutputNode(self.modelService.getName(), f"{self.modelService.getMqttTopic()}/set")
        labels = ["Disabled"]
        labels.extend(self.modelService.getLabels())
        selector = HomeAssistantSelector(f"{self.modelService.getName()} Trainer", f"{self.modelService.getName()}-Trainer", labels)
        joinNode = JoinNode(f"{self.modelService.getName()} Joiner", 3)

        mqttInput = MqttInputNode(self.modelService.getName(), f"{self.modelService.getMqttTopic()}/state")
        outputSensor = HomeAssistantSensor(f"{self.modelService.getName()} Prediction",f"{self.modelService.getName()}-Prediction", "payload.value")

        selector.addWire(joinNode)
        joinNode.addWire(mqttOutput)

        mqttInput.addWire(outputSensor)

        result = []
        result.extend(selector.generate())
        result.extend(joinNode.generate())
        result.extend(mqttOutput.generate())

        result.extend(mqttInput.generate())
        result.extend(outputSensor.generate())

        return json.dumps(result, indent=4)