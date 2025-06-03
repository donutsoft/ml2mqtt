import sqlite3
import struct
import logging
import threading
from dataclasses import dataclass, field
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Union
from pathlib import Path
import json
from enum import Enum

@dataclass
class EntityKey:
    name: str
    type: int
    display_type: str = field(init=False)
    significance: float = field(default=0)

    def __post_init__(self):
        if self.type == ModelStore.TYPE_FLOAT:
            self.display_type = "float"
        elif self.type == ModelStore.TYPE_STRING:
            self.display_type = "string"

@dataclass
class ModelObservation:
    def __init__(self, time: int, label: str, sensorValues: Dict[str, Any]):
        self.time = time
        self.label = label
        self.sensorValues = sensorValues

    @property
    def display_time(self) -> str:
        return datetime.fromtimestamp(self.time, tz=timezone.utc).isoformat()


@dataclass
class ProcessorEntry:
    id: int
    type: str
    params: Dict[str, Any]
    order: int

class ProcessorType(Enum):
    PREPROCESSOR = "Preprocessors"
    POSTPROCESSOR = "Postprocessors"

class ModelStore:
    TYPE_INT = 0
    TYPE_FLOAT = 1
    TYPE_STRING = 2

    TYPE_FORMATS = {
        TYPE_FLOAT: "f",
        TYPE_STRING: "f",  # stored as int reference to string table
    }

    def __init__(self, modelPath: str):
        self.modelPath = modelPath
        self.logger = logging.getLogger(__name__)
        self.lock = threading.Lock()
        self._db = sqlite3.connect(modelPath, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._cursor = self._db.cursor()

        self._createTables()
        self._populateSensors()
        self._populateStringTable()

        self.logger.info("ModelStore initialized with model: %s", modelPath)

    def _createTables(self) -> None:
        with self.lock, self._db:
            cursor = self._db.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS SensorKeys (name TEXT PRIMARY KEY, type INTEGER)")
            cursor.execute("CREATE TABLE IF NOT EXISTS Observations (time INTEGER, label TEXT, data BLOB)")
            cursor.execute("CREATE TABLE IF NOT EXISTS StringTable (name TEXT)")
            cursor.execute("CREATE TABLE IF NOT EXISTS Settings (name TEXT PRIMARY KEY, value)")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Preprocessors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT,
                    params TEXT,
                    order_num INTEGER
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Postprocessors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT,
                    params TEXT,
                    order_num INTEGER
                )
            """)
            self._db.commit()

    def _populateSensors(self) -> None:
        self._entityKeys: List[EntityKey] = []
        for name, type_ in self._cursor.execute("SELECT name, type FROM SensorKeys"):
            self._entityKeys.append(EntityKey(name, type_))
        self._entityKeySet: Set[str] = set(sk.name for sk in self._entityKeys)

    def _populateStringTable(self) -> None:
        self._stringTable: Dict[str, int] = dict((row[1], row[0]) for row in self._cursor.execute("SELECT ROWID, name FROM StringTable"))
        self._reverseStringTable: Dict[int, str] = {v: k for k, v in self._stringTable.items()}

    def _getStringId(self, string: str) -> int:
        if string not in self._stringTable:
            with self.lock, self._db:
                self._db.execute("INSERT INTO StringTable (name) VALUES (?)", (string,))
                self._db.commit()
            self._populateStringTable()
        return self._stringTable[string]

    def _getType(self, variable: Any) -> int:
        if isinstance(variable, int):
            return self.TYPE_FLOAT
        elif isinstance(variable, float):
            return self.TYPE_FLOAT
        elif isinstance(variable, str):
            try:
                float(variable)
                return self.TYPE_FLOAT
            except ValueError:
                return self.TYPE_STRING
        raise ValueError(f"Unsupported type: {variable}")

    def _getDbValue(self, variable: Any) -> Union[int, float]:
        varType = self._getType(variable)
        if varType == self.TYPE_STRING:
            stringId = self._getStringId(variable)
            return stringId
        elif varType == self.TYPE_FLOAT:
            return float(variable)
        raise ValueError(f"Unsupported type: {variable}")

    def _getValue(self, entityKey: EntityKey, value: Any) -> Any:
        if entityKey.type == self.TYPE_STRING:
            return self._reverseStringTable[value] if value in self._reverseStringTable else None
        else:
            return value

    def _generateFormatString(self, size: int = -1) -> str:
        formatStr = ""
        currentSize = 0
        for entityKey in self._entityKeys:
            if 0 < size <= currentSize:
                break
            formatStr += self.TYPE_FORMATS[entityKey.type]
            currentSize += 4
        return formatStr

    def _addSensorType(self, name: str, value: Any) -> None:
        sensorType = self._getType(value)
        with self.lock, self._db:
            try:
                self._db.execute("INSERT INTO SensorKeys (name, type) VALUES (?, ?)", (name, sensorType))
                self._db.commit()
            except sqlite3.IntegrityError:
                pass
        if not name in self._entityKeySet:
            self._entityKeys.append(EntityKey(name, sensorType))
            self._entityKeySet.add(name)

    def sortEntityValues(self, entityMap: Dict[str, Any], forTraining: bool) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        remaining = set(entityMap.keys())
        # Filter entity values based on known entity keys
        for entity in self._entityKeys:
            val = entityMap.get(entity.name)
            values[entity.name] = val
            remaining.discard(entity.name)

        if forTraining:
            for key in remaining:
                self._addSensorType(key, entityMap[key])
                values[key] = entityMap[key]

        return values

    def addObservation(self, label: str, sensors: Dict[str, Any], assignedTime: Optional[float] = None) -> None:
        if assignedTime is None:
            assignedTime = time.time()
        for sensor in sensors:
            if sensor not in self._entityKeySet:
                self._addSensorType(sensor, sensors[sensor])
        self.logger.info(f"Observation to be added: {sensors}")
        formatStr = self._generateFormatString()
        try:
            values = [self._getDbValue(sensors.get(entity.name)) for entity in self._entityKeys]
            packed = struct.pack(formatStr, *values)

            with self.lock, self._db:
                self._db.execute("INSERT INTO Observations (time, label, data) VALUES (?, ?, ?)", (assignedTime, label, packed))
                self._db.commit()
        except Exception as e:
            self.logger.exception("Exception while adding observation")

    def getObservations(self) -> List[ModelObservation]:
        self._cursor.execute("SELECT time, label, data FROM Observations ORDER BY time DESC")
        observations: List[ModelObservation] = []
        for timeVal, label, data in self._cursor.fetchall():
            formatStr = self._generateFormatString(len(data))
            unpacked = struct.unpack(formatStr, data)
            sensorValues = {
                entity.name: self._getValue(entity, unpacked[i] if i < len(unpacked) else None)
                for i, entity in enumerate(self._entityKeys)
            }
            sensorValues = {k: v for k, v in sensorValues.items() if v is not None}
            observations.append(ModelObservation(timeVal, label, sensorValues))
        return observations

    def getEntityKeys(self):
        return self._entityKeys

    def getModelSize(self):
        return Path(self.modelPath).stat().st_size

    def _getSetting(self, name: str, default_value: Any) -> Any:
        with self._db as conn:
            row = conn.execute("SELECT value FROM Settings WHERE name = ?", (name,)).fetchone()
            return row[0] if row else default_value

    def getDict(self, name: str) -> Optional[Dict[str, Any]]:
        return json.loads(self._getSetting(name, "{}"))

    def saveDict(self, name: str, value: Dict[str, Any]) -> None:
        self._saveSetting(name, json.dumps(value))

    def _saveSetting(self, name: str, value: Any) -> None:
        with self.lock, self._db:
            self._db.execute("INSERT OR REPLACE INTO Settings (name, value) VALUES (?, ?)", (name, value))
            self._db.commit()

    def setMqttTopic(self, mqttTopic: str) -> None:
        self._saveSetting("mqtt_topic", mqttTopic)

    def getMqttTopic(self) -> Optional[str]:
        return self._getSetting("mqtt_topic", None)

    def setName(self, name: str) -> None:
        self._saveSetting("name", name)

    def getName(self) -> Optional[str]:
        return self._getSetting("name", None)

    def initialize_schema_from_entity_names(self, entity_names: List[str], default_type: int = TYPE_FLOAT) -> None:
        """
        Initializes or re-initializes the SensorKeys table from a list of entity names.
        All existing SensorKeys will be cleared.
        """
        with self.lock, self._db:
            # Clear existing SensorKeys
            self._db.execute("DELETE FROM SensorKeys")

            # Insert new entity names
            for name in entity_names:
                self._db.execute("INSERT INTO SensorKeys (name, type) VALUES (?, ?)", (name, default_type))

            self._db.commit()

        # Refresh internal sensor key caches
        self._populateSensors()
        self.logger.info(f"Initialized schema with {len(entity_names)} entities: {entity_names}")

    def getLabels(self) -> List[str]:
        return [row[0] for row in self._cursor.execute("SELECT DISTINCT label FROM Observations ORDER BY label ASC")]

    def deleteObservationsByLabel(self, label: str) -> None:
        with self.lock, self._db:
            self._db.execute("DELETE FROM Observations WHERE label = ?", (label,))
            self._db.commit()

    def deleteObservation(self, time: int) -> None:
        with self.lock, self._db:
            self._db.execute("DELETE FROM Observations WHERE time = ?", (time,))
            self._db.commit()

    def deleteObservationsSince(self, timestamp: float) -> None:
        """
        Deletes all observations with a timestamp greater than or equal to the provided timestamp.
        """
        with self.lock, self._db:
            self._db.execute("DELETE FROM Observations WHERE time >= ?", (timestamp,))
            self._db.commit()

    def deleteEntity(self, entityName: str) -> None:
        if entityName not in self._entityKeySet:
            raise ValueError("Entity not found")
        
        observations = self.getObservations()
        self._entityKeys = [ek for ek in self._entityKeys if ek.name != entityName]
        self._entityKeySet.remove(entityName)

        with self.lock, self._db:
            self._db.execute("DELETE FROM SensorKeys WHERE name = ?", (entityName,))
            self._db.execute("DELETE FROM Observations")
            self._db.commit()

        for observation in observations:
            observation.sensorValues.pop(entityName)
            self.addObservation(observation.label, observation.sensorValues, observation.time)

    # -- Processor management --

    def addPreprocessor(self, type_: str, params: Dict[str, Any], order: Optional[int] = None) -> None:
        self._addProcessor(ProcessorType.PREPROCESSOR, type_, params, order)

    def addPostprocessor(self, type_: str, params: Dict[str, Any], order: Optional[int] = None) -> int:
        """Add a new postprocessor and return its ID."""
        return self._addProcessor(ProcessorType.POSTPROCESSOR, type_, params, order)

    def deletePreprocessor(self, id_: int) -> None:
        self._deleteProcessor(ProcessorType.PREPROCESSOR, id_)

    def deletePostprocessor(self, id_: int) -> None:
        self._deleteProcessor(ProcessorType.POSTPROCESSOR, id_)

    def reorderPreprocessors(self, idOrderList: List[int]) -> None:
        self._reorderProcessors(ProcessorType.PREPROCESSOR, idOrderList)

    def reorderPostprocessors(self, idOrderList: List[int]) -> None:
        self._reorderProcessors(ProcessorType.POSTPROCESSOR, idOrderList)

    def _addProcessor(self, processorType: ProcessorType, type_: str, params: Dict[str, Any], order: Optional[int]) -> int:
        table = processorType.value
        if order is None:
            cursor = self._db.cursor()
            cursor.execute(f"SELECT COALESCE(MAX(order_num), 0) + 1 FROM {table}")
            order = cursor.fetchone()[0]
        with self.lock, self._db:
            cursor = self._db.cursor()
            cursor.execute(
                f"INSERT INTO {table} (type, params, order_num) VALUES (?, ?, ?)",
                (type_, json.dumps(params), order)
            )
            self._db.commit()
            return cursor.lastrowid

    def _deleteProcessor(self, processorType: ProcessorType, id_: int) -> None:
        table = processorType.value
        with self.lock, self._db:
            self._db.execute(f"DELETE FROM {table} WHERE ROWID = ?", (id_,))
            self._db.commit()

    def _reorderProcessors(self, processorType: ProcessorType, idOrderList: List[int]) -> None:
        table = processorType.value
        with self.lock, self._db:
            for order, id_ in enumerate(idOrderList):
                self._db.execute(f"UPDATE {table} SET order_num = ? WHERE ROWID = ?", (order, id_))
            self._db.commit()

    def getPreprocessors(self) -> List[ProcessorEntry]:
        return self._getProcessors(ProcessorType.PREPROCESSOR)

    def getPostprocessors(self) -> List[ProcessorEntry]:
        return self._getProcessors(ProcessorType.POSTPROCESSOR)

    def _getProcessors(self, processorType: ProcessorType) -> List[ProcessorEntry]:
        table = processorType.value
        cursor = self._db.cursor()
        cursor.execute(f"SELECT ROWID, type, params, order_num FROM {table} ORDER BY order_num ASC")
        return [ProcessorEntry(id=row[0], type=row[1], params=json.loads(row[2]), order=row[3]) for row in cursor.fetchall()]

    def close(self) -> None:
        try:
            with self.lock:
                self._db.close()
        except sqlite3.ProgrammingError:
            pass