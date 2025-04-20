from SkillStore import SkillStore
from classifiers.RandomForest import RandomForest
from MqttClient import MqttClient
import logging
import json

class SkillService:
    def __init__(self, mqttClient, skillstore: SkillStore):
        self.logger = logging.getLogger("ml2mqtt")
        self._mqttClient = mqttClient
        self._skillstore = skillstore
        self._randomForest = RandomForest()
        self._previousLabel = None
        self._sensorsSeen = set()
        self._populateModel()

    def dispose(self):
        self._mqttClient.unsubscribe(self._skillstore.getMqttTopic() + "/set", self.predictLabel)
        self._mqttClient.unsubscribe(self._skillstore.getMqttTopic() + "/label", self.addObservation)
    
    def subscribeToMqttTopics(self):
        self.logger.info("Subscribing to MQTT topics")
        self._mqttClient.subscribe(self._skillstore.getMqttTopic() + "/set", self.predictLabel)
        self._mqttClient.subscribe(self._skillstore.getMqttTopic() + "/label", self.addObservation)

    def _populateModel(self):
        self._randomForest.populateDataframe(self._skillstore.getObservations())

    def addObservation(self, label):
        self._skillstore.addObservation(label, self._skillstore.getSensorRecentValues())
        self._populateModel()

    def predictLabel(self, msg):
        sensorValues = json.loads(msg)
        self._skillstore.setSensorRecentValue(sensorValues["entity_id"], sensorValues["state"])

        self._sensorsSeen.add(sensorValues["entity_id"])

        print(str(self._sensorsSeen) + "\n" +  str(self._skillstore.getSensorRecentValues().keys()) + "\n\n\n")

        sensorRecentValues = self._skillstore.getSensorRecentValues()
        if len(self._sensorsSeen) < len(sensorRecentValues.keys()):
            return
        
        self.logger.info("Predicting label for: " + str(self._sensorsSeen))
        currentLabel = self._randomForest.predictLabel(sensorRecentValues)
        self._sensorsSeen.clear()

        if currentLabel != self._previousLabel:
            self._previousLabel = currentLabel
            self._mqttClient.publish(self._skillstore.getMqttTopic() + "/state", json.dumps({"state": currentLabel}))
            self.logger.info("Predicted label: %s", currentLabel)
        else:
            self.logger.info("No change in label: %s", currentLabel)
    
    def getMqttTopic(self):
        return self._skillstore.getMqttTopic()
    
    def setMqttTopic(self, mqttTopic):
        self._skillstore.setMqttTopic(mqttTopic)

    def getName(self):
        return self._skillstore.getName()
    
    def setDefaultValue(self, sensorName, defaultValue):
        self._skillstore.setDefaultValue(sensorName, defaultValue)

    def setName(self, skillName):
        self._skillstore.setName(skillName)