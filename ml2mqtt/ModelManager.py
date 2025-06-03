from pathlib import Path
from typing import Dict, List
from MqttClient import MqttClient
from ModelService import ModelService
from ModelStore import ModelStore


class ModelManager:
    def __init__(self, mqttClient: MqttClient, modelsDir: str):
        self._mqttClient = mqttClient
        self._models: Dict[str, ModelService] = {}
        self._modelsDir: Path = Path(modelsDir)
        self._modelsDir.mkdir(exist_ok=True)

        for modelFile in self._modelsDir.glob("*.db"):
            modelName = self.getModelName(modelFile)
            service = ModelService(self._mqttClient, ModelStore(str(modelFile)))
            service.subscribeToMqttTopics()
            self._models[modelName] = service

    def addModel(self, model: str) -> ModelService:
        key = model.lower() # Assuming 'model' is a base name like "My Model"
        if key in self._models:
            # This case should ideally be handled by the caller checking modelExists first.
            # If called for an already loaded model, returning the existing service might be an option,
            # but raising an error is also valid if the expectation is to only call addModel for new additions.
            raise ValueError(f"Model '{key}' is already loaded and registered.")

        dbPath = self._modelsDir / f"{key}.db"

        # ModelStore constructor will use existing dbPath if it exists, or create if not.
        # CREATE TABLE IF NOT EXISTS in ModelStore._createTables handles table creation.
        store = ModelStore(str(dbPath))
        service = ModelService(self._mqttClient, store)

        # Ensure the model name stored in the service/DB is consistent if needed.
        # ModelService currently gets its name from ModelStore, which gets it from the DB file stem.
        # If dbPath is "data/models/my model.db", store.getName() would be "my model".
        # This seems consistent with 'key'.

        self._models[key] = service
        service.subscribeToMqttTopics() # Ensure MQTT topics are subscribed for the newly added/loaded model
        return service

    def modelExists(self, modelName: str) -> bool:
        return modelName.lower() in self._models

    def getModelName(self, modelPath: Path) -> str:
        return modelPath.stem.lower()

    def listModels(self) -> List[str]:
        return [self.getModelName(f) for f in self._modelsDir.glob("*.db")]

    def removeModel(self, modelName: str) -> None:
        key = modelName.lower()
        if key in self._models:
            self._models[key].dispose()
            del self._models[key]

        dbPath = self._modelsDir / f"{key}.db"
        if dbPath.exists():
            dbPath.unlink()

    def getModel(self, modelName: str) -> ModelService:
        key = modelName.lower()
        return self._models[key]

    def getModels(self) -> Dict[str, ModelService]:
        return self._models

    def __contains__(self, modelName: str) -> bool:
        return self.modelExists(modelName)

    def __getitem__(self, modelName: str) -> ModelService:
        return self.getModel(modelName)