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
        key = model.lower()
        if key in self._models:
            raise ValueError(f"Model '{model}' already exists.")

        dbPath = self._modelsDir / f"{key}.db"
        service = ModelService(self._mqttClient, ModelStore(str(dbPath)))
        self._models[key] = service
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