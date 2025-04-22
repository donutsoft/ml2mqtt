import sqlite3
import struct
import time
import logging
import threading
class SkillStore:
    TYPE_INT = 0
    TYPE_FLOAT = 1
    TYPE_STRING = 2


    def __init__(self, skill, unknownValue=9999.0):
        self.lock = threading.Lock()
        self._db = sqlite3.connect(skill, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")

        self._cursor = self._db.cursor()
        self._createTables()
        self._populateSensors()
        self._populateStringTable()
        self._unknownValue = self._getSetting("unknown_value", unknownValue)
        self.logger = logging.getLogger("ml2mqtt")
        self.logger.log(logging.INFO, "SkillStore initialized with skill: %s", skill)

    def _createTables(self):
        with self.lock, self._db:
            cursor = self._db.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS SensorKeys (name VARCHAR(100) PRIMARY KEY, type INTEGER, default_value BLOB)")
            cursor.execute("CREATE TABLE IF NOT EXISTS Observations (time INTEGER, label VARCHAR(100), data BLOB)")
            cursor.execute("CREATE TABLE IF NOT EXISTS StringTable (name TEXT)")
            cursor.execute("CREATE TABLE IF NOT EXISTS Settings (name TEXT PRIMARY KEY, value)")
            self._db.commit()

    def _populateSensors(self):
        self._sensorKeys = []
        for row in self._cursor.execute("SELECT name, type, default_value FROM SensorKeys").fetchall():
            print("Row: " + str(row))
            self._sensorKeys.append({"name": row[0], "type": row[1], "default_value": struct.unpack(self._generateFormatType(row[1]), row[2])[0]})


        self._sensorKeySet = set(map(lambda x: x["name"], self._sensorKeys))

    def _populateStringTable(self):
        self._stringTable = {}
        self._stringTable = dict(map(lambda row: (row[1], row[0]), self._cursor.execute("SELECT ROWID, name FROM StringTable")))
        self._reverseStringTable = dict(map(lambda row: (row[1], row[0]), self._stringTable.items()))

    def _getStringId(self, string):
        if not string in self._stringTable:
            with self.lock, self._db:
                cursor = self._db.cursor()
                cursor.execute("INSERT INTO StringTable (name) VALUES (?)", (string,))
                self._db.commit()
            self._populateStringTable()
        return self._stringTable[string]

    def _getType(self, variable):
        self.logger.debug("Get type called for: " + str(variable))
        if isinstance(variable, int):
            self.logger.debug(str(variable) + "is an int")
            return SkillStore.TYPE_INT
        elif isinstance(variable, float):
            self.logger.debug(str(variable) + "is an float")
            return SkillStore.TYPE_FLOAT
        elif isinstance(variable, str):
            try:
                float(variable)
                if '.' in variable:
                    return SkillStore.TYPE_FLOAT
                else:
                    return SkillStore.TYPE_INT
            except:
                return SkillStore.TYPE_STRING
        else:
            raise ValueError("Unsupported type for: " + str(variable))
        
    def _getDbValue(self, variable):
        type = self._getType(variable)
        if type == SkillStore.TYPE_STRING:
            return self._getStringId(variable)
        elif type == SkillStore.TYPE_INT:
            return int(variable)
        elif type == SkillStore.TYPE_FLOAT:
            return float(variable)
        else:
            raise ValueError("Unsupported type for: " + str(variable))
        
    def _getValue(self, sensorKey, value):
        if sensorKey["type"] == SkillStore.TYPE_STRING:
            return self._reverseStringTable[value]
        else:
            return value
        
    def _generateFormatType(self, type):
        if type == SkillStore.TYPE_INT:
            return "i"
        elif type == SkillStore.TYPE_FLOAT:
            return "f"
        elif type == SkillStore.TYPE_STRING:
            return "i"
        else:
            raise ValueError("Unsupported type")
        
    def _generateFormatString(self, size=-1):
        formatString = ""
        currentSize = 0
        for sensorKey in self._sensorKeys:
            if size > 0 and currentSize >= size:
                break
            formatString += self._generateFormatType(sensorKey["type"])
            currentSize += 4
        return formatString
           
    def _addSensorType(self, sensorName, value):
        print("Adding sensor type: " + str(sensorName) + " with value: " + str(value))
        sensorType = self._getType(value)
        unknownValue = self._getDbValue(str(self._unknownValue) if sensorType == SkillStore.TYPE_STRING else self._unknownValue)

        default_value = struct.pack(self._generateFormatType(sensorType), unknownValue)
        with self.lock, self._db:
            try:
                cursor = self._db.cursor()
                cursor.execute("INSERT INTO SensorKeys (name, type, default_value) VALUES (?, ?, ?)", (sensorName, sensorType, default_value,))
                self._db.commit()
                self._sensorKeys.append({"name": sensorName, "type": sensorType, "default_value": unknownValue})
                self._sensorKeySet.add(sensorName)
            except sqlite3.IntegrityError:
                pass

    def sortEntityValues(self, entityMap, forTraining: bool):
        sensorValues = []
        remaining = set(entityMap.keys())
        for i, sensorKey in enumerate(self._sensorKeys):
            if sensorKey["name"] not in entityMap:
                sensorValues.append(self._getDbValue(sensorKey["default_value"]))
            else:
                if entityMap[sensorKey["name"]] == "unknown" or entityMap[sensorKey["name"]] == "unavailable":
                    sensorValues.append(self._getDbValue(sensorKey["default_value"]))
                else:
                    sensorValues.append(entityMap[sensorKey["name"]])
            remaining.remove(sensorKey["name"])
        
        if forTraining:
            for entityKey in remaining:
                self._addSensorType(entityKey, entityMap[entityKey])
                sensorValues.append(self._getDbValue(entityMap[entityKey]))

        return sensorValues

    def addObservation(self, label, sensors):
        for sensor in sensors:
            if sensor not in self._sensorKeySet:
                self._addSensorType(sensor, sensors[sensor])

        formatString = self._generateFormatString()
        values = []
        for sensor in self._sensorKeys:
            if sensor["name"] in sensors:
                values.append(self._getDbValue(sensors[sensor["name"]]))
            else:
                values.append(self._getDbValue(sensor["default_value"]))
        packedValues = struct.pack(formatString, *values)

        with self.lock, self._db:
            cursor = self._db.cursor()
            cursor.execute("INSERT INTO Observations (time, label, data) VALUES (?, ?, ?)", (time.time(), label, packedValues))
            self._db.commit()

    def getObservations(self):
        self._cursor.execute("SELECT * FROM Observations ORDER BY time DESC")
        observations = []
        for time, label, data in self._cursor.fetchall():
            formatString = self._generateFormatString(len(data))
            unpackedData = struct.unpack(formatString, data)
            sensorValues = {}
            observation = {
                "label": label,
                "time": time,
                "sensorValues": sensorValues
            }

            for i, sensorKey in enumerate(self._sensorKeys):
                if i < len(unpackedData):
                    sensorValues[sensorKey["name"]] = self._getValue(sensorKey, unpackedData[i])
                else:
                    sensorValues[sensorKey["name"]] = self._getValue(sensorKey, sensorKey["default_value"])

            observations.append(observation)
        return observations
    
    def setDefaultValue(self, sensorName, value):
        if sensorName == "*":
            self._saveSetting("unknown_value", value)
            return

        if sensorName not in self._sensorKeySet:
            raise ValueError("Sensor not found")
        sensorType = self._getType(value)
        if sensorType != self._sensorKeys[sensorName]["type"]:
            raise ValueError("Type mismatch")
        default_value = struct.pack(self._generateFormatType(sensorType), self._getDbValue(value))
        with self.lock, self._db:
            cursor = self._db.cursor()
            cursor.execute("UPDATE SensorKeys SET default_value = ? WHERE name = ?", (default_value, sensorName))
            self._db.commit()

    def _getSetting(self, name, default_value):
        self._cursor.execute("SELECT value FROM Settings WHERE name = ?", (name,)) 
        row = self._cursor.fetchone()
        return row[0] if row else default_value
    
    def _saveSetting(self, name, value):
        with self.lock, self._db:
            cursor = self._db.cursor()
            cursor.execute("INSERT OR REPLACE INTO Settings (name, value) VALUES (?, ?)", (name, value))

    def setMqttTopic(self, mqttTopic):
        self._saveSetting("mqtt_topic", mqttTopic)

    def getMqttTopic(self):
        return self._getSetting("mqtt_topic", None)
    
    def setName(self, name):
        self._saveSetting("name", name)

    def getName(self):
        return self._getSetting("name", None)
    
    def getLabels(self):
        return [row[0] for row in self._cursor.execute("SELECT DISTINCT label FROM Observations ORDER BY label ASC")]
    
    def close(self):
        try:
            with self.lock:
                self._db.close()
        except sqlite3.ProgrammingError:
            pass