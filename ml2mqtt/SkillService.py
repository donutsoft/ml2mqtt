import logging
import json
from typing import Any, Dict, List, Optional, Union

from SkillStore import SkillStore, SkillObservation, SensorKey
from classifiers.RandomForest import RandomForest, RandomForestParams
from classifiers.KNNClassifier import KNNClassifier, KNNParams
from paho.mqtt.client import Client as MqttClient

DISABLED_LABEL = "Disabled"


class SkillService:
    def __init__(self, mqttClient: MqttClient, skillstore: SkillStore):
        self.logger: logging.Logger = logging.getLogger("ml2mqtt")
        self._mqttClient: MqttClient = mqttClient
        self._skillstore: SkillStore = skillstore
        self._previousLabel: Optional[str] = None

        self._model: Union[RandomForest, KNNClassifier]
        self._modelType: str
        self._allParams: Dict[str, Dict[str, Any]] = {}
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
        settings = self._skillstore.getDict('model_settings') or {}
        self._modelType = settings.get("model_type", "RandomForest")
        self._allParams = settings.get("model_parameters", {})

        paramsForThisModel = self._allParams.get(self._modelType, {})

        self.logger.info(f"Loading with settings {settings}")

        if self._modelType == "KNN":
            self._model = KNNClassifier(params=paramsForThisModel)
        else:
            self._model = RandomForest(params=paramsForThisModel)

        observations = self._skillstore.getObservations()
        self._model.populateDataframe(observations)

    def getSensorKeys(self) -> List[SensorKey]:
        features = self._model.getFeatureImportance() or {}
        entities = self._skillstore.getSensorKeys()
        for entity in entities:
            entity.significance = features.get(entity.name, 0.0)
        return entities

    def getAccuracy(self) -> Optional[float]:
        return self._model.getAccuracy()

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
        except json.JSONDecodeError:
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
            self._populateModel()

        prediction = self._model.predictLabel(entityValues)

        if prediction != self._previousLabel:
            self._previousLabel = prediction
            topic = self.getMqttTopic()
            self._mqttClient.publish(f"{topic}/state", json.dumps({"state": prediction}))
            self.logger.info("Predicted label: %s", prediction)

    def getMqttTopic(self) -> str:
        return self._skillstore.getMqttTopic() or ""

    def setMqttTopic(self, mqttTopic: str) -> None:
        self._skillstore.setMqttTopic(mqttTopic)

    def getName(self) -> str:
        return self._skillstore.getName() or ""

    def setName(self, skillName: str) -> None:
        self._skillstore.setName(skillName)

    def setDefaultValue(self, sensorName: str, defaultValue: Any) -> None:
        self._skillstore.setDefaultValue(sensorName, defaultValue)

    def getObservations(self) -> List[SkillObservation]:
        return self._skillstore.getObservations()

    def getModelSize(self) -> float:
        return self._skillstore.getModelSize()

    def getLabels(self) -> List[str]:
        return self._skillstore.getLabels()

    def getLabelStats(self) -> Optional[Dict[str, Any]]:
        return self._model.getLabelStats()

    def optimizeParameters(self) -> None:
        self._model.optimizeParameters(self._skillstore.getObservations())
        self._allParams[self._modelType] = self._model.getModelParameters()
        self._skillstore.saveDict("model_settings", self.getModelSettings())

    def getModelSettings(self) -> Dict[str, Any]:
        return {
            "model_type": self._modelType,
            "model_parameters": self._allParams
        }

    def setModelSettings(self, settings: Dict[str, Any]) -> None:
        self._modelType = settings.get("model_type", "RandomForest")
        self._allParams = settings.get("model_parameters", {})
        self._skillstore.saveDict("model_settings", settings)
        self._populateModel()
