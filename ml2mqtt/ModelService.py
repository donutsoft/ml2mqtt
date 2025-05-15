import logging
import json
from typing import Any, Dict, List, Optional, Union

from ModelStore import ModelStore, ModelObservation, EntityKey
from classifiers.RandomForest import RandomForest, RandomForestParams
from classifiers.KNNClassifier import KNNClassifier, KNNParams
from MqttClient import MqttClient
from postprocessors.PostprocessorFactory import PostprocessorFactory
from postprocessors.base import BasePostprocessor
from preprocessors.base import BasePreprocessor
from preprocessors.PreprocessorFactory import PreprocessorFactory
from nodered.nodered_generator import NodeRedGenerator
DISABLED_LABEL = "Disabled"


class ModelService:
    def __init__(self, mqttClient: MqttClient, modelstore: ModelStore):
        self._mqttClient = mqttClient
        self._modelstore: ModelStore = modelstore
        self._model = None
        self._logger = logging.getLogger(__name__)
        self._postProcessorFactory = PostprocessorFactory()
        self._postprocessors: List[BasePostprocessor] = []

        self._preprocessorFactory = PreprocessorFactory()
        self._preprocessors: List[BasePreprocessor] = []
        
        self._modelType: str
        self._allParams: Dict[str, Dict[str, Any]] = {}
        self._recentMqtt = []
        self._populateModel()
        self._loadPostprocessors()
        self._loadPreprocessors()

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


    def _loadPreprocessors(self) -> None:
        """Load postprocessors from model settings."""
        preprocessors = self._modelstore.getPreprocessors()
        self._preprocessors = []
        
        for preprocessor_data in preprocessors:
            try:
                postprocessor = self._preprocessorFactory.create(preprocessor_data.type, preprocessor_data.id, preprocessor_data.params)
                self._preprocessors.append(postprocessor)
            except ValueError as e:
                self._logger.warning(f"Failed to load preprocessor: {e}")


    def getEntityKeys(self) -> List[EntityKey]:
        features = self._model.getFeatureImportance() or {}
        entities = self._modelstore.getEntityKeys()
        for entity in entities:
            entity.significance = features.get(entity.name, 0.0)
        return entities

    def getAccuracy(self) -> Optional[float]:
        return self._model.getAccuracy()

    def predictLabel(self, msg: Any) -> None:
        self._recentMqtt.append(msg)
        if len(self._recentMqtt) > 10:
            self._recentMqtt.pop(0)

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

        previousEntityMap = self._modelstore.getDict("mqtt_observations")
        if "history" in previousEntityMap:
            previousEntityMap['history'].append(entityMap)
            if len(previousEntityMap['history']) > 10:
                previousEntityMap['history'].pop(0)
        else:
            previousEntityMap['history'] = [entityMap]    
        self._modelstore.saveDict("mqtt_observations", previousEntityMap)

        # Apply Preprocessors
        processor_storage = self._modelstore.getDict("processor_storage")
        for preprocessor in self._preprocessors:
            if not preprocessor.dbId in processor_storage:
                processor_storage[preprocessor.dbId] = {}
            entityMap = preprocessor.process(entityMap, processor_storage[preprocessor.dbId])
            if not entityMap:
                self._logger.debug("No entity values to process.")
                return
        self._modelstore.saveDict("processor_storage", processor_storage)

        if not entityMap:
            self._logger.debug("No entity values to process.")
            return        

        entityValues = {k: v for k, v in entityMap.items() if v is not None}

        if label != DISABLED_LABEL:
            learningType = self.getLearningType()
            if learningType == "LAZY":
                prediction, _ = self._model.predictLabel(entityValues)
                if prediction != label:
                    entityValues = self._modelstore.sortEntityValues(entityMap, True)
                    self._logger.info("Adding training observation for label: %s", label)
                    self._modelstore.addObservation(label, entityValues)
                    self._populateModel()
            elif learningType == "EAGER":
                entityValues = self._modelstore.sortEntityValues(entityMap, True)
                self._logger.info("Adding training observation for label: %s", label)
                self._modelstore.addObservation(label, entityValues)
                self._populateModel()

        prediction, confidence = self._model.predictLabel(entityValues)
        confidence = round(confidence, 4)
        # Apply postprocessors
        observation = entityValues
        for postprocessor in self._postprocessors:
            observation, prediction = postprocessor.process(observation, prediction, confidence)
            if prediction is None:
                return

        topic = self.getMqttTopic()
        self._mqttClient.publish(f"{topic}/state", json.dumps({"state": prediction, "confidence": confidence}))
        self._logger.info(f"Predicted label: {prediction} with confidence {confidence}")

    def getMqttTopic(self) -> str:
        return self._modelstore.getMqttTopic() or ""

    def setMqttTopic(self, mqttTopic: str) -> None:
        self._modelstore.setMqttTopic(mqttTopic)

    def getName(self) -> str:
        return self._modelstore.getName() or ""

    def setName(self, modelName: str) -> None:
        self._modelstore.setName(modelName)

    def getObservations(self) -> List[ModelObservation]:
        return self._modelstore.getObservations()

    def getModelSize(self) -> int:
        return self._modelstore.getModelSize()

    def getLabels(self) -> List[str]:
        return self._modelstore.getLabels() + self.getModelConfig("labels", [])

    def deleteEntity(self, entityName: str) -> None:
        self._modelstore.deleteEntity(entityName)
        # Rebuild the model after entity deletion
        self._populateModel()

    def getLabelStats(self) -> Optional[Dict[str, Any]]:
        labelStats = self._model.getLabelStats() or {}
        for extraLabel in self.getLabels():
            if not extraLabel in labelStats.keys():   
                labelStats[extraLabel] = {
                    "support":0,
                    "precision": 0,
                    "recall": 0,
                    "f1": 0,
                }        
        return labelStats

    def deleteObservationsByLabel(self, label: str) -> None:
        """Delete all observations with the given label."""
        self._modelstore.deleteObservationsByLabel(label)

        presavedLabels = self.getModelConfig("labels", [])
        presavedLabels.remove(label)
        self.setModelConfig("labels", presavedLabels)

        # Rebuild the model after deletion
        self._populateModel()

    def deleteObservation(self, time: int) -> None:
        """Delete an observation by its timestamp."""
        self._modelstore.deleteObservation(time)
        # Rebuild the model after deletion
        self._populateModel()

    def deleteObservationsSince(self, timestamp: int) -> None:
            """Delete an observation by its timestamp."""
            self._modelstore.deleteObservationsSince(timestamp)
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
        """Get list of postprocessors."""
        return self._postprocessors

    def getPreprocessors(self) -> List[BasePreprocessor]:
        """Get list of preprocessors."""
        return self._preprocessors

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

    def addPreprocessor(self, type: str, params: Dict[str, Any]) -> None:
        """Add a new preprocessor."""
        try:
            # First add to database to get the ID
            dbId = self._modelstore.addPreprocessor(type, params)
            # Then create the postprocessor instance
            preprocessor = self._preprocessorFactory.create(type, dbId, params)
            self._preprocessors.append(preprocessor)
            self.deleteObservationsSince(0)
        except Exception as e:
            # If postprocessor creation fails, delete from database.
            if 'dbId' in locals():
                self._modelstore.deletePreprocessor(dbId)
            raise e

    def removePostprocessor(self, index: int) -> None:
        """Remove a postprocessor by index."""
        if 0 <= index < len(self._postprocessors):
            deletedProcessor = self._postprocessors.pop(index)
            
            self._modelstore.deletePostprocessor(deletedProcessor.dbId)

    def removePreprocessor(self, index: int) -> None:
        """Remove a preprocessor by index."""
        if 0 <= index < len(self._preprocessors):
            deletedProcessor = self._preprocessors.pop(index)
            
            self._modelstore.deletePreprocessor(deletedProcessor.dbId)
            self.deleteObservationsSince(0)

    def reorderPreprocessors(self, from_index: int, to_index: int) -> None:
        """Reorder preprocessors."""
        if 0 <= from_index < len(self._preprocessors) and 0 <= to_index < len(self._preprocessors):
            self._logger.info("Previous preprocessors: %s", list(map(lambda p: p, self._preprocessors)))
            preprocessor = self._preprocessors.pop(from_index)
            self._preprocessors.insert(to_index, preprocessor)
            self._logger.info("Reordering preprocessors: %s", list(map(lambda p: p, self._preprocessors)))
            self._modelstore.reorderPreprocessors(map(lambda p: p.dbId, self._preprocessors))
            self.deleteObservationsSince(0)

    def reorderPostprocessors(self, from_index: int, to_index: int) -> None:
        """Reorder postprocessors."""
        if 0 <= from_index < len(self._postprocessors) and 0 <= to_index < len(self._postprocessors):
            self._logger.info("Previous postprocessors: %s", list(map(lambda p: p, self._postprocessors)))
            postprocessor = self._postprocessors.pop(from_index)
            self._postprocessors.insert(to_index, postprocessor)
            self._logger.info("Reordering postprocessors: %s", list(map(lambda p: p, self._postprocessors)))
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

    def getMostRecentMqttObservations(self):
        previousObservations = self._modelstore.getDict("mqtt_observations")
        if 'history' in previousObservations:
            return previousObservations['history']
        else:
            return []
    
    def setModelConfig(self, key, value):
        current = self._modelstore.getDict("config")
        current[key] = value
        self._modelstore.saveDict("config", current)
    
    def getModelConfig(self, key, default):
        config = self._modelstore.getDict("config")
        if key in config:
            return config[key]
        else:
            return default

    def generateNodeRed(self) -> str:
        nodeRedGenerator = NodeRedGenerator(self)
        return nodeRedGenerator.generate()
    
    def getRecentMqtt(self) -> str:
        return self._recentMqtt