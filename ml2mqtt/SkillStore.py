import sqlite3
import struct
import time
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Union
from pathlib import Path


@dataclass
class SensorKey:
    name: str
    type: int
    default_value: Any
    display_type: str = field(init=False)
    significance: float = field(default=0)

    def __post_init__(self):
        if self.type == SkillStore.TYPE_INT:
           self.display_type = "int"
        elif self.type == SkillStore.TYPE_FLOAT:
            self.display_type = "float"
        elif self.type == SkillStore.TYPE_STRING:
            self.display_type = "string"


@dataclass
class SkillObservation:
    time: float
    label: str
    sensorValues: Dict[str, Any]
    display_time: str = field(init=False)

    def __post_init__(self):
        self.display_time = datetime.fromtimestamp(self.time).isoformat()

class SkillStore:
    TYPE_INT = 0
    TYPE_FLOAT = 1
    TYPE_STRING = 2

    TYPE_FORMATS = {
        TYPE_INT: "i",
        TYPE_FLOAT: "f",
        TYPE_STRING: "i",  # stored as int reference to string table
    }

    def __init__(self, modelPath: str, unknownValue: float = 9999.0):
        self.modelPath = modelPath
        self.logger = logging.getLogger("ml2mqtt")
        self.lock = threading.Lock()
        self._db = sqlite3.connect(modelPath, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._cursor = self._db.cursor()
        self._unknownValue: Union[str, float] = unknownValue

        self._createTables()
        self._populateSensors()
        self._populateStringTable()

        self._unknownValue = self._getSetting("unknown_value", self._unknownValue)
        self.logger.info("SkillStore initialized with skill: %s", modelPath)

    def _createTables(self) -> None:
        with self.lock, self._db:
            cursor = self._db.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS SensorKeys (name TEXT PRIMARY KEY, type INTEGER, default_value BLOB)")
            cursor.execute("CREATE TABLE IF NOT EXISTS Observations (time INTEGER, label TEXT, data BLOB)")
            cursor.execute("CREATE TABLE IF NOT EXISTS StringTable (name TEXT)")
            cursor.execute("CREATE TABLE IF NOT EXISTS Settings (name TEXT PRIMARY KEY, value)")
            self._db.commit()

    def _populateSensors(self) -> None:
        self._sensorKeys: List[SensorKey] = []
        for name, type_, default_blob in self._cursor.execute("SELECT name, type, default_value FROM SensorKeys"):
            default_value = struct.unpack(self.TYPE_FORMATS[type_], default_blob)[0]
            self._sensorKeys.append(SensorKey(name, type_, default_value))
        self._sensorKeySet: Set[str] = set(sk.name for sk in self._sensorKeys)

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
            return self.TYPE_INT
        elif isinstance(variable, float):
            return self.TYPE_FLOAT
        elif isinstance(variable, str):
            try:
                float(variable)
                return self.TYPE_FLOAT if '.' in variable else self.TYPE_INT
            except ValueError:
                return self.TYPE_STRING
        raise ValueError(f"Unsupported type: {variable}")

    def _getDbValue(self, variable: Any) -> Union[int, float]:
        varType = self._getType(variable)
        if varType == self.TYPE_STRING:
            return self._getStringId(variable)
        elif varType == self.TYPE_INT:
            return int(variable)
        elif varType == self.TYPE_FLOAT:
            return float(variable)
        raise ValueError(f"Unsupported type: {variable}")

    def _getValue(self, sensorKey: SensorKey, value: Any) -> Any:
        return self._reverseStringTable[value] if sensorKey.type == self.TYPE_STRING else value

    def _generateFormatString(self, size: int = -1) -> str:
        formatStr = ""
        currentSize = 0
        for sensorKey in self._sensorKeys:
            if 0 < size <= currentSize:
                break
            formatStr += self.TYPE_FORMATS[sensorKey.type]
            currentSize += 4
        return formatStr

    def _addSensorType(self, name: str, value: Any) -> None:
        sensorType = self._getType(value)
        unknownValue = self._getDbValue(str(self._unknownValue) if sensorType == self.TYPE_STRING else self._unknownValue)
        packedDefault = struct.pack(self.TYPE_FORMATS[sensorType], unknownValue)
        with self.lock, self._db:
            try:
                self._db.execute("INSERT INTO SensorKeys (name, type, default_value) VALUES (?, ?, ?)", (name, sensorType, packedDefault))
                self._db.commit()
                self._sensorKeys.append(SensorKey(name, sensorType, unknownValue))
                self._sensorKeySet.add(name)
            except sqlite3.IntegrityError:
                pass

    def sortEntityValues(self, entityMap: Dict[str, Any], forTraining: bool) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        remaining = set(entityMap.keys())
        # Filter entity values based on known sensor keys
        for sensor in self._sensorKeys:
            val = entityMap.get(sensor.name, sensor.default_value)
            if val in ("unknown", "unavailable"):
                val = sensor.default_value
            values[sensor.name] = self._getDbValue(val)
            remaining.discard(sensor.name)

        if forTraining:
            for key in remaining:
                self._addSensorType(key, entityMap[key])
                values[sensor.name] = self._getDbValue(entityMap[key])

        return values

    def addObservation(self, label: str, sensors: Dict[str, Any]) -> None:
        for sensor in sensors:
            if sensor not in self._sensorKeySet:
                self._addSensorType(sensor, sensors[sensor])

        formatStr = self._generateFormatString()
        values = [self._getDbValue(sensors.get(sensor.name, sensor.default_value)) for sensor in self._sensorKeys]
        packed = struct.pack(formatStr, *values)

        with self.lock, self._db:
            self._db.execute("INSERT INTO Observations (time, label, data) VALUES (?, ?, ?)", (time.time(), label, packed))
            self._db.commit()

    def getObservations(self) -> List[SkillObservation]:
        self._cursor.execute("SELECT time, label, data FROM Observations ORDER BY time DESC")
        observations: List[SkillObservation] = []

        for timeVal, label, data in self._cursor.fetchall():
            formatStr = self._generateFormatString(len(data))
            unpacked = struct.unpack(formatStr, data)
            sensorValues = {
                sensor.name: self._getValue(sensor, unpacked[i] if i < len(unpacked) else sensor.default_value)
                for i, sensor in enumerate(self._sensorKeys)
            }
            observations.append(SkillObservation(timeVal, label, sensorValues))
        return observations

    def setDefaultValue(self, sensorName: str, value: Any) -> None:
        if sensorName == "*":
            self._saveSetting("unknown_value", value)
            return

        if sensorName not in self._sensorKeySet:
            raise ValueError("Sensor not found")

        sensor = next(s for s in self._sensorKeys if s.name == sensorName)
        if self._getType(value) != sensor.type:
            raise ValueError("Type mismatch")

        packed = struct.pack(self.TYPE_FORMATS[sensor.type], self._getDbValue(value))
        with self.lock, self._db:
            self._db.execute("UPDATE SensorKeys SET default_value = ? WHERE name = ?", (packed, sensorName))
            self._db.commit()

    def getSensorKeys(self):
        return self._sensorKeys
    
    def getModelSize(self):
        return Path(self.modelPath).stat().st_size

    def _getSetting(self, name: str, default_value: Any) -> Any:
        self._cursor.execute("SELECT value FROM Settings WHERE name = ?", (name,))
        row = self._cursor.fetchone()
        return row[0] if row else default_value

    def _saveSetting(self, name: str, value: Any) -> None:
        with self.lock, self._db:
            self._db.execute("INSERT OR REPLACE INTO Settings (name, value) VALUES (?, ?)", (name, value))

    def setMqttTopic(self, mqttTopic: str) -> None:
        self._saveSetting("mqtt_topic", mqttTopic)

    def getMqttTopic(self) -> Optional[str]:
        return self._getSetting("mqtt_topic", None)

    def setName(self, name: str) -> None:
        self._saveSetting("name", name)

    def getName(self) -> Optional[str]:
        return self._getSetting("name", None)

    def getLabels(self) -> List[str]:
        return [row[0] for row in self._cursor.execute("SELECT DISTINCT label FROM Observations ORDER BY label ASC")]

    def close(self) -> None:
        try:
            with self.lock:
                self._db.close()
        except sqlite3.ProgrammingError:
            pass
