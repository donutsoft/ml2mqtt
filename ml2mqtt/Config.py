import json
import os
from pathlib import Path

class Config:
    def __init__(self):
        options_path = Path("/data/options.json")
        settings_path = Path("settings.json")
        
        self.config = {}
        if options_path.exists():
            with open(options_path, "r") as file:
                options = json.load(file)
                self.config = {
                    "mqtt": {
                        "server": options.get("mqtt_server", "core-mosquitto"),
                        "port": options.get("mqtt_port", 1883),
                        "username": options.get("mqtt_username", "mqtt"),
                        "password": options.get("mqtt_password", "mqtt")
                    }
                }
        elif settings_path.exists():
            with open(settings_path, "r") as file:
                self.config = json.load(file)
        else:
            raise FileNotFoundError("Neither /data/options.json nor settings.json found")

    def getValue(self, keyName, valueName=None):
        if valueName is None:
            return self.config.get(keyName, {})
        else:
            return self.config.get(keyName, {}).get(valueName)
