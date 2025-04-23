import logging
import json
from typing import Any, Dict, List, Optional

from SkillStore import SkillStore
from classifiers.RandomForest import RandomForest
from paho.mqtt.client import Client as MqttClient  # Or your MQTT client wrapper
from SkillStore import SkillObservation

DISABLED_LABEL = "Disabled"

class SkillService:
    def __init__(self, mqttClient: MqttClient, skillstore: SkillStore):
        self.logger: logging.Logger = logging.getLogger("ml2mqtt")
        self._mqttClient: MqttClient = mqttClient
        self._skillstore: SkillStore = skillstore
        self._randomForest: RandomForest = RandomForest()
        self._previousLabel: Optional[str] = None
        self._populateModel()

    def dispose(self) -> None:
        topic = self.getMqttTopic()
        self._mqttClient.unsubscribe(f"{topic}/set", self.predictLabel)
        self._skillstore.close()

    def subscribeToMqttTopics(self) -> None:
        topic = self.getMqttTopic()
        self.logger.info("Subscribing to MQTT topic: %s/set", topic)
        self._mqttClient.subscribe(f"{topic}/set", self.predictLabel)

    def _populateModel(self) -> None:
        observations = self._skillstore.getObservations()
        self._randomForest.populateDataframe(observations)

    def predictLabel(self, msg: Any) -> None:
        messageStr: str
        if hasattr(msg, "payload"):
            try:
                messageStr = msg.payload.decode()
            except Exception as e:
                self.logger.warning("Could not decode MQTT payload: %s", e)
                return
        else:
            messageStr = str(msg)

        try:
            entities: List[Dict[str, Any]] = json.loads(messageStr)
        except json.JSONDecodeError as e:
            self.logger.warning("Invalid JSON: %s", messageStr)
            return

        label: str = DISABLED_LABEL
        entityMap: Dict[str, Any] = {}

        for entity in entities:
            if "label" in entity:
                label = entity["label"]
            elif "entity_id" in entity and "state" in entity:
                entityMap[entity["entity_id"]] = entity["state"]

        if not entityMap:
            self.logger.debug("No entity values to process.")
            return

        entityValues = self._skillstore.sortEntityValues(entityMap, label != DISABLED_LABEL)

        if label != DISABLED_LABEL:
            self.logger.info("Adding training observation for label: %s", label)
            self._skillstore.addObservation(label, entityMap)

        prediction = self._randomForest.predictLabel(entityValues)

        if prediction != self._previousLabel:
            self._previousLabel = prediction
            topic = self.getMqttTopic()
            self._mqttClient.publish(f"{topic}/state", json.dumps({"state": prediction}))
            self.logger.info("Predicted label: %s", prediction)

    def getMqttTopic(self) -> str:
        return self._skillstore.getMqttTopic()

    def setMqttTopic(self, mqttTopic: str) -> None:
        self._skillstore.setMqttTopic(mqttTopic)

    def getName(self) -> str:
        return self._skillstore.getName()

    def setDefaultValue(self, sensorName: str, defaultValue: Any) -> None:
        self._skillstore.setDefaultValue(sensorName, defaultValue)

    def setName(self, skillName: str) -> None:
        self._skillstore.setName(skillName)

    def getObservations(self) -> List[SkillObservation]:
        return self._skillstore.getObservations()

    def getLabels(self) -> List[str]:
        return self._skillstore.getLabels()