import sqlite3
import struct
import time
import logging
import os
class SkillStore:
    TYPE_INT = 0
    TYPE_FLOAT = 1
    TYPE_STRING = 2


    def __init__(self, skill, unknownValue=9999):
        self._db = sqlite3.connect(f"skills/{skill}", check_same_thread=False)
        self._cursor = self._db.cursor()
        self._createTables()
        self._populateSensors()
        self._populateStringTable()
        self._unknownValue = self._getSetting("unknown_value", unknownValue)
        self.logger = logging.getLogger("ml2mqtt")


    def _createTables(self):
        self._cursor.execute("CREATE TABLE IF NOT EXISTS SensorKeys (name VARCHAR(100), type INTEGER, default_value BLOB)")
        self._cursor.execute("CREATE TABLE IF NOT EXISTS Observations (time INTEGER, label VARCHAR(100), data BLOB)")
        self._cursor.execute("CREATE TABLE IF NOT EXISTS StringTable (name TEXT)")
        self._cursor.execute("CREATE TABLE IF NOT EXISTS Settings (name TEXT PRIMARY KEY, value)")
        self._cursor.execute("CREATE TABLE IF NOT EXISTS SensorRecentValues (name TEXT PRIMARY KEY, value)")
        self._db.commit()

    def _populateSensors(self):
        self._cursor.execute("SELECT name, type, default_value FROM SensorKeys")
        self._sensorKeys = list(map(lambda row: { "name": row[0], "type": row[1], "default_value": row[2] }, self._cursor.fetchall()))
        self._sensorKeySet = set(map(lambda x: x["name"], self._sensorKeys))

    def _populateStringTable(self):
        self._cursor.execute("SELECT ROWID, name FROM StringTable")
        self._stringTable = {}
        self._stringTable = dict(map(lambda row: (row[1], row[0]), self._cursor.fetchall()))
        self._reverseStringTable = dict(map(lambda row: (row[1], row[0]), self._stringTable.items()))

    def _getStringId(self, string):
        if string in self._stringTable:
            return self._stringTable[string]
        else:
            self._cursor.execute("INSERT INTO StringTable (name) VALUES (?)", (string,))
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
                num = float(variable)
                if '.' in variable:
                    return SkillStore.TYPE_FLOAT
                else:
                    return SkillStore.TYPE_INT
            except:
                return SkillStore.TYPE_STRING
        else:
            raise ValueError("Unsupported type for: " + str(variable))
        
    def _getDbValue(self, variable):
        if self._getType(variable) == SkillStore.TYPE_STRING:
            return self._getStringId(variable)
        else:
            if isinstance(variable, str):
                try:
                    num = float(variable)
                    if '.' in variable:
                        return num
                    else:
                        return int(variable)
                except:
                    raise ValueError("Unsupported type for: " + str(variable))
            else:
                return variable
        
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
        sensorType = self._getType(value)
        unknownValue = self._getDbValue(str(self._unknownValue) if sensorType == SkillStore.TYPE_STRING else self._unknownValue)

        default_value = struct.pack(self._generateFormatType(sensorType), unknownValue)
        self._cursor.execute("INSERT INTO SensorKeys (name, type, default_value) VALUES (?, ?, ?)", (sensorName, sensorType, default_value,))
        self._db.commit()
        self._sensorKeys.append({"name": sensorName, "type": sensorType, "default_value": unknownValue})
        self._sensorKeySet.add(sensorName)

    def getSensorRecentValues(self):
        self._cursor.execute("SELECT name, value FROM SensorRecentValues")
        rows = self._cursor.fetchall()
        sensorValues = {}
        for row in rows:
            name, value = row
            sensorValues[name] = value
        return sensorValues
    
    def setSensorRecentValue(self, sensorName, value):
        if value == "unknown" and sensorName not in self._sensorKeySet:
            return

        self._cursor.execute("INSERT OR REPLACE INTO SensorRecentValues (name, value) VALUES (?, ?)", (sensorName, value))
        self._db.commit()

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

        self._cursor.execute("INSERT INTO Observations (time, label, data) VALUES (?, ?, ?)", (time.time(), label, packedValues))
        self._db.commit()

    def getObservations(self):
        self._cursor.execute("SELECT * FROM Observations")
        rows = self._cursor.fetchall()
        observations = []
        for row in rows:
            time, label, data = row
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
                    print("Value not found:" + str(sensorKey))
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
        self._cursor.execute("UPDATE SensorKeys SET default_value = ? WHERE name = ?", (default_value, sensorName))
        self._db.commit()

    def _getSetting(self, name, default_value):
        self._cursor.execute("SELECT value FROM Settings WHERE name = ?", (name,)) 
        result = self._cursor.fetchone()
        if result is None:
            return default_value
        else:
            return result[0]
    
    def _saveSetting(self, name, value):
        self._cursor.execute("INSERT OR REPLACE INTO Settings (name, value) VALUES (?, ?)", (name, value))
        self._db.commit()

    def setMqttTopic(self, mqttTopic):
        self._saveSetting("mqtt_topic", mqttTopic)

    def getMqttTopic(self):
        return self._getSetting("mqtt_topic", None)
    
    def setName(self, name):
        self._saveSetting("name", name)

    def getName(self):
        return self._getSetting("name", None)