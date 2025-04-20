import json

class Config:
    def __init__(self):
        self.config = json.loads(open("config.json", "r").read())

    def getValue(self, keyName, valueName=None):
        if valueName == None: 
            return self.config[keyName]
        else:
            return self.config[keyName][valueName]