from SkillStore import SkillStore
from classifiers.RandomForest import RandomForest
import logging
import json

class SkillService:
    def __init__(self, mqttClient, skillstore: SkillStore):
        self.logger = logging.getLogger("ml2mqtt")
        self._mqttClient = mqttClient
        self._skillstore = skillstore
        self._randomForest = RandomForest()
        self._previousLabel = None
        self._populateModel()

    def dispose(self):
        self._mqttClient.unsubscribe(self._skillstore.getMqttTopic() + "/set", self.predictLabel)
        self._skillstore.close()
    
    def subscribeToMqttTopics(self):
        self.logger.info("Subscribing to MQTT topics")
        self._mqttClient.subscribe(self._skillstore.getMqttTopic() + "/set", self.predictLabel)

    def _populateModel(self):
        self._randomForest.populateDataframe(self._skillstore.getObservations())

    def predictLabel(self, msg):
        entities = json.loads(msg)
        assigned_label = "Disabled"
        entityMap = {}
        for entity in entities:
            if "label" in entity:
                assigned_label = entity["label"]
            else:
                entityMap[entity["entity_id"]] = entity["state"]
        
        entityValues = self._skillstore.sortEntityValues(entityMap, not assigned_label == "Disabled")
        if assigned_label != "Disabled":
            self._skillstore.addObservation(assigned_label, entityMap)

        currentLabel = self._randomForest.predictLabel(entityValues)
        
        if currentLabel != self._previousLabel:
            self._previousLabel = currentLabel
            self._mqttClient.publish(self._skillstore.getMqttTopic() + "/state", json.dumps({"state": currentLabel}))
            self.logger.info("Predicted label: %s", currentLabel)
    
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

    def getObservations(self):
        return self._skillstore.getObservations()
    
    def getLabels(self):
        return self._skillstore.getLabels()