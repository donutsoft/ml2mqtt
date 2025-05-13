from .nodered_types import HomeAssistantSelector, JoinNode, MqttOutputNode, HomeAssistantSensor, MqttInputNode, HomeAssistantState, HomeAssistantStateChanged, DelayNode
import json

class NodeRedGenerator:
    def __init__(self, modelService):
        self.modelService = modelService

    def generate(self):
        result = []

        mqttInput = MqttInputNode(self.modelService.getName(), f"{self.modelService.getMqttTopic()}/state")
        outputSensor = HomeAssistantSensor(f"{self.modelService.getName()} Prediction",f"{self.modelService.getName()}_Prediction", "payload.value")
        mqttInput.addWire(outputSensor)

        mqttOutput = MqttOutputNode(self.modelService.getName(), f"{self.modelService.getMqttTopic()}/set")
        labels = ["Disabled"]
        labels.extend(self.modelService.getLabels())
        selector = HomeAssistantSelector(f"{self.modelService.getName()} Trainer", f"{self.modelService.getName()}_trainer", labels)

        # Add an extra join input for the label selector
        joinNode = JoinNode(f"{self.modelService.getName()} Joiner", self.modelService.getModelConfig("input_count", 1) + 1)
        stateChanged = HomeAssistantStateChanged("ADD ALL SOURCE ENTITIES HERE", None)
        joinNode.addWire(mqttOutput)


        # Create HomeAssistant state reader for every entity

        trainerName = f"select.{self.modelService.getName().lower().replace('-','_').replace(' ','_')}_trainer"
        trainerState = HomeAssistantState(f"{self.modelService.getName()} Trainer (Ignore error on first deploy)", trainerName)
        trainerState.setPayload("{ 'label': $entity().state }", "jsonata")
        states = [trainerState]
        states += [
            HomeAssistantState(f"CHANGE ME TO A SOURCE ENTITY")
            for i in range(self.modelService.getModelConfig("input_count", 1))
        ]

        for state in states:
            state.addWire(joinNode)
            result.extend(state.generate())

        stateChanged.addWires(states)
        delayNode = DelayNode("selector delay", 500)
        delayNode.addWires(states)
        selector.addWire(delayNode)

        result.extend(delayNode.generate())
        result.extend(selector.generate())
        result.extend(joinNode.generate())
        result.extend(mqttOutput.generate())

        result.extend(mqttInput.generate())
        result.extend(outputSensor.generate())        
        result.extend(stateChanged.generate())

        return json.dumps(result, indent=4)