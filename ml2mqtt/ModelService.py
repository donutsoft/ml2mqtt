import logging
import json
from typing import Any, Dict, List, Optional, Union

from ModelStore import ModelStore, ModelObservation, EntityKey
from classifiers.RandomForest import RandomForest, RandomForestParams
from classifiers.KNNClassifier import KNNClassifier, KNNParams
from MqttClient import MqttClient
from postprocessors.PostprocessorFactory import PostprocessorFactory
from postprocessors.base import BasePostprocessor

DISABLED_LABEL = "Disabled"


class ModelService:
    def __init__(self, mqttClient: MqttClient, modelstore: ModelStore):
        self._mqttClient = mqttClient
        self._modelstore: ModelStore = modelstore
        self._model = None
        self._logger = logging.getLogger(__name__)
        self._postProcessorFactory = PostprocessorFactory()
        self._postprocessors: List[BasePostprocessor] = []

        self._modelType: str
        self._allParams: Dict[str, Dict[str, Any]] = {}
        self._populateModel()
        self._loadPostprocessors()

    def dispose(self) -> None:
        topic = self.getMqttTopic()
        self._mqttClient.unsubscribe(f"{topic}/set", self.predictLabel)
        self._modelstore.close()

    def subscribeToMqttTopics(self) -> None:
        topic = self.getMqttTopic()
        self._logger.info("Subscribing to MQTT topic: %s/set", topic)
        self._mqttClient.subscribe(f"{topic}/set", self.predictLabel)

    def _populateModel(self) -> None:
        settings = self._modelstore.getDict('model_settings') or {}
        self._modelType = settings.get("model_type", "RandomForest")
        self._allParams = settings.get("model_parameters", {})

        paramsForThisModel = self._allParams.get(self._modelType, {})

        self._logger.info(f"Loading with settings {settings}")

        if self._modelType == "KNN":
            self._model = KNNClassifier(params=paramsForThisModel)
        else:
            self._model = RandomForest(params=paramsForThisModel)

        observations = self._modelstore.getObservations()
        self._model.populateDataframe(observations)

    def _loadPostprocessors(self) -> None:
        """Load postprocessors from model settings."""
        postProcessors = self._modelstore.getPostprocessors()
        self._postprocessors = []
        
        for postprocessor_data in postProcessors:
            try:
                postprocessor = self._postProcessorFactory.create(postprocessor_data.type, postprocessor_data.id, postprocessor_data.params)
                self._postprocessors.append(postprocessor)
            except ValueError as e:
                self._logger.warning(f"Failed to load postprocessor: {e}")

    def getEntityKeys(self) -> List[EntityKey]:
        features = self._model.getFeatureImportance() or {}
        entities = self._modelstore.getEntityKeys()
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
                self._logger.warning("Could not decode MQTT payload: %s", e)
                return
        else:
            messageStr = str(msg)

        try:
            entities: List[Dict[str, Any]] = json.loads(messageStr)
        except json.JSONDecodeError:
            self._logger.warning("Invalid JSON: %s", messageStr)
            return

        label: str = DISABLED_LABEL
        entityMap: Dict[str, Any] = {}

        for entity in entities:
            if "label" in entity:
                label = entity["label"]
            elif "entity_id" in entity and "state" in entity:
                entityMap[entity["entity_id"]] = entity["state"]

        if not entityMap:
            self._logger.debug("No entity values to process.")
            return

        entityValues = self._modelstore.sortEntityValues(entityMap, label != DISABLED_LABEL)

        if label != DISABLED_LABEL:
            learningType = self.getLearningType()
            if learningType == "EAGER" or (learningType == "LAZY" and self._model.predictLabel(entityValues) != label):
                self._logger.info("Adding training observation for label: %s", label)
                self._modelstore.addObservation(label, entityMap)
                self._populateModel()
                
        prediction = self._model.predictLabel(entityValues)
        
        # Apply postprocessors
        observation = entityValues
        for postprocessor in self._postprocessors:
            observation, prediction = postprocessor.process(observation, prediction)
            if prediction is None:
                return

        topic = self.getMqttTopic()
        self._mqttClient.publish(f"{topic}/state", json.dumps({"state": prediction}))
        self._logger.info("Predicted label: %s", prediction)

    def getMqttTopic(self) -> str:
        return self._modelstore.getMqttTopic() or ""

    def setMqttTopic(self, mqttTopic: str) -> None:
        self._modelstore.setMqttTopic(mqttTopic)

    def getName(self) -> str:
        return self._modelstore.getName() or ""

    def setName(self, modelName: str) -> None:
        self._modelstore.setName(modelName)

    def setDefaultValue(self, sensorName: str, defaultValue: Any) -> None:
        self._modelstore.setDefaultValue(sensorName, defaultValue)

    def getObservations(self) -> List[ModelObservation]:
        return self._modelstore.getObservations()

    def getModelSize(self) -> int:
        return self._modelstore.getModelSize()

    def getLabels(self) -> List[str]:
        return self._modelstore.getLabels()

    def deleteEntity(self, entityName: str) -> None:
        self._modelstore.deleteEntity(entityName)
        # Rebuild the model after entity deletion
        self._populateModel()

    def getLabelStats(self) -> Optional[Dict[str, Any]]:
        return self._model.getLabelStats()

    def deleteObservationsByLabel(self, label: str) -> None:
        """Delete all observations with the given label."""
        self._modelstore.deleteObservationsByLabel(label)
        # Rebuild the model after deletion
        self._populateModel()

    def deleteObservation(self, time: int) -> None:
        """Delete an observation by its timestamp."""
        self._modelstore.deleteObservation(time)
        # Rebuild the model after deletion
        self._populateModel()

    def optimizeParameters(self) -> None:
        best_params = self._model.optimizeParameters(self._modelstore.getObservations())

        modelSettings = self.getModelSettings()
        modelSettings["model_parameters"] = modelSettings.get("model_parameters", {})
        modelSettings["model_parameters"][self._modelType] = best_params
        self._modelstore.saveDict("model_settings", modelSettings)

    def getModelSettings(self) -> Dict[str, Any]:
        settings = self._modelstore.getDict('model_settings') or {}
        if not settings:
            settings = {
                "model_type": "RandomForest",
                "model_parameters": {
                    "RandomForest": {
                        "n_estimators": 100,
                        "max_depth": None,
                        "min_samples_split": 2,
                        "min_samples_leaf": 1,
                        "max_features": "sqrt",
                        "class_weight": None,
                        "bootstrap": True,
                        "oob_score": False
                    }, "KNN": {
                        "n_neighbors": 5,
                        "weights": "uniform",
                        "algorithm": "auto",
                        "leaf_size": 30,
                        "metric": "minkowski",
                        "p": 2
                    }
                }
            }
        return settings

    def setModelSettings(self, settings: Dict[str, Any]) -> None:
        self._logger.info(f"Setting model settings: {settings}");
        self._modelType = settings.get("model_type", "RandomForest")
        self._allParams = settings.get("model_parameters", {})
        self._modelstore.saveDict("model_settings", settings)
        self._populateModel()

    def getPostprocessors(self) -> List[BasePostprocessor]:
        """Get list of post processors."""
        return self._postprocessors

    def addPostprocessor(self, type: str, params: Dict[str, Any]) -> None:
        """Add a new postprocessor."""
        try:
            # First add to database to get the ID
            dbId = self._modelstore.addPostprocessor(type, params)
            # Then create the postprocessor instance
            postprocessor = self._postProcessorFactory.create(type, dbId, params)
            self._postprocessors.append(postprocessor)
        except Exception as e:
            # If postprocessor creation fails, delete from database
            if 'dbId' in locals():
                self._modelstore.deletePostprocessor(dbId)
            raise e

    def removePostprocessor(self, index: int) -> None:
        """Remove a postprocessor by index."""
        if 0 <= index < len(self._postprocessors):
            deletedProcessor = self._postprocessors.pop(index)
            
            self._modelstore.deletePostprocessor(deletedProcessor.dbId)

    def reorderPostprocessors(self, from_index: int, to_index: int) -> None:
        """Reorder postprocessors."""
        if 0 <= from_index < len(self._postprocessors) and 0 <= to_index < len(self._postprocessors):
            self._logger.error("Previous postprocessors: %s", list(map(lambda p: p, self._postprocessors)))
            postprocessor = self._postprocessors.pop(from_index)
            self._postprocessors.insert(to_index, postprocessor)
            self._logger.error("Reordering postprocessors: %s", list(map(lambda p: p, self._postprocessors)))
            self._modelstore.reorderPostprocessors(map(lambda p: p.dbId, self._postprocessors))

    def getLearningType(self):
        settings = self.getModelSettings() or {}
        learningType = settings.get("learning_type", "DISABLED")
        self._logger.info(f"Getting learning type: {learningType}")
        return learningType
    
    def setLearningType(self, learningType: str) -> None:
        settings = self.getModelSettings() or {}
        settings["learning_type"] = learningType
        self._logger.info(f"Setting learning type: {learningType}")
        self._modelstore.saveDict("model_settings", settings)
    