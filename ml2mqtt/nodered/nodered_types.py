import random
import string
import json
from typing import List

def generate_random_id() -> str:
    """Generate a random 16-character alphanumeric ID."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))

class Node:
    def __init__(self, node_name):
        self.nodeName = node_name
        self.id = generate_random_id()
        self.server_id = 'qm2m0pytzpm6tf7c'
        self.wires = []

    def generate(self):
        pass

    def addWire(self, otherNode):
        self.wires.append(otherNode.id)

    def addWires(self, otherNodes):
        self.wires.append([item.id for item in otherNodes])

class HomeAssistantSelector(Node):
    def __init__(self, node_name: str, entity_name: str, options: List[str]):
        super().__init__(node_name)
        self.entity_name = entity_name
        self.options = options
        self.entity_config_id = generate_random_id()

    def generate(self):
        return [
        {
            "id": self.id,
            "type": "ha-select",
            "name": self.nodeName,
            "inputs": 0,
            "outputs": 1,
            "entityConfig": self.entity_config_id,
            "value": "payload",
            "valueType": "msg",
            "outputProperties": [
                {
                    "property": "payload",
                    "propertyType": "msg",
                    "value": "",
                    "valueType": "value"
                }
            ],
            "wires": self.wires
        },
        {
            "id": self.entity_config_id,
            "type": "ha-entity-config",
            "name": self.nodeName,
            "entityType": "select",
            "haConfig": [
                {
                    "property": "name",
                    "value": self.entity_name
                },
                {
                    "property": "options",
                    "value": self.options
                }
            ]
        }
    ]

class JoinNode(Node):
    def __init__(self, node_name: str, count: int):
        super().__init__(node_name)
        self.count = count
    
    def generate(self):
        return [{
            "id": self.id,
            "type": "join",
            "name": "Join Node",
            "mode": "custom",
            "build": "array",
            "property": "payload",
            "propertyType": "msg",
            "key": "payload.entity_id",
            "joiner": "\\n",
            "joinerType": "str",
            "useparts": False,
            "accumulate": False,
            "count": str(self.count),
            "wires": self.wires
        }]

class MqttOutputNode(Node):
    def __init__(self, node_name: str, topic: str):
        super().__init__(node_name)
        self.topic = topic
        self.qos = ""
        self.retain = ""
    
    def generate(self):
        return [{
        "id": self.id,
        "type": "mqtt out",
        "name": self.topic,
        "topic": self.topic,
        "qos": self.qos,
        "retain": self.retain,
        "respTopic": "",
        "contentType": "",
        "userProps": "",
        "correl": "",
        "expiry": "",
        "broker": "",
        "wires": self.wires
    }]

class MqttInputNode(Node):
    def __init__(self, node_name: str, topic: str):
        super().__init__(node_name)
        self.topic = topic

    def generate(self):
        return [{
        "id": self.id,
        "type": "mqtt in",
        "z": "8d8011b612b07a68",
        "name": self.topic,
        "topic": self.topic,
        "qos": "2",
        "datatype": "auto-detect",
        "nl": False,
        "rap": True,
        "rh": 0,
        "inputs": 0,
        "wires": self.wires
        }]
    
class HomeAssistantSensor(Node):
    def __init__(self, node_name: str, entity_name: str, state_property: str = "payload"):
        super().__init__(node_name)
        self.entity_name = entity_name
        self.state_property = state_property
        self.entity_config_id = generate_random_id()

    def generate(self):
        return [
            {
                "id": self.id,
                "type": "ha-sensor",
                "z": "8d8011b612b07a68",
                "name": self.entity_name,
                "entityConfig": self.entity_config_id,
                "version": 0,
                "state": self.state_property,
                "stateType": "msg",
                "attributes": [],
                "inputOverride": "allow",
                "outputProperties": [],
                "wires": self.wires
            },
            {
                "id": self.entity_config_id,
                "type": "ha-entity-config",
                "deviceConfig": "",
                "name": self.entity_name,
                "version": "6",
                "entityType": "sensor",
                "haConfig": [
                    {"property": "name", "value": self.entity_name}
                ],
                "resend": False,
                "debugEnabled": False
            }
        ]

class HomeAssistantState(Node):
    def __init__(self, node_name, entity_id=None):
        super().__init__(node_name)
        self.entity_id = entity_id
        self.payload_value = ""
        self.payload_value_type = "entity"


    def setPayload(self, value, type):
        self.payload_value = value
        self.payload_value_type = type

    def generate(self):
        return [
            {
                "id": self.id,
                "type": "api-current-state",
                "name": self.nodeName,
                "version": 3,
                "outputs": 1,
                "halt_if": "",
                "halt_if_type": "str",
                "halt_if_compare": "is",
                "state_type": "str",
                "blockInputOverrides": True,
                "outputProperties": [
                    {
                        "property": "payload",
                        "propertyType": "msg",
                        "value": self.payload_value,
                        "valueType": self.payload_value_type
                    }
                ],
                "for": "0",
                "forType": "num",
                "forUnits": "minutes",
                "override_topic": False,
                "state_location": "payload",
                "override_payload": "msg",
                "entity_location": "data",
                "override_data": "msg",
                "entity_id": self.entity_id,
                "wires": self.wires
            }
        ]

class HomeAssistantStateChanged(Node):
    def __init__(self, node_name: str, entities: List[str]):
        super().__init__(node_name)
        self.entities = entities

    def generate(self):
        return [{
            "id": self.id,
            "type": "server-state-changed",
            "name": self.nodeName,
            "outputOnlyOnStateChange": True,
            "outputProperties": [
                {"property": "payload", "propertyType": "msg", "value": "", "valueType": "entityState"},
                {"property": "data", "propertyType": "msg", "value": "", "valueType": "eventData"},
                {"property": "topic", "propertyType": "msg", "value": "", "valueType": "triggerId"}
            ],
            "wires": self.wires
        }]
