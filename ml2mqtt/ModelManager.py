from pathlib import Path
from typing import Dict, List, Optional
import shutil
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

    def addModel(self, model: str, source_db_path: Optional[str] = None) -> ModelService:
        key = model.lower()
        if key in self._models:
            raise ValueError(f"Model '{model}' already exists.")

        target_db_path = self._modelsDir / f"{key}.db" # Renamed dbPath to target_db_path for clarity

        if source_db_path:
            source_path = Path(source_db_path)
            if source_path.exists() and source_path.is_file():
                self._modelsDir.mkdir(parents=True, exist_ok=True) # Ensure modelsDir exists
                shutil.copy2(source_db_path, target_db_path)
                # Consider adding logging here if a logger is available
                # print(f"Copied database from {source_db_path} to {target_db_path}")
            # else:
                # Optionally log a warning if source_db_path doesn't exist
                # print(f"Warning: Source database path {source_db_path} not found or not a file. Creating new database for model {key}.")

        # ModelStore will open the copied DB if target_db_path now exists,
        # or create a new one if it doesn't (e.g. source_db_path was not provided or invalid)
        service = ModelService(self._mqttClient, ModelStore(str(target_db_path)))
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