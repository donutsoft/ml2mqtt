import os
from SkillService import SkillService
from SkillStore import SkillStore

class SkillManager:
    def __init__(self, mqttClient):
        self._skills = {}
        self._mqttClient = mqttClient
        for skillFile in os.listdir("skills/"):
            self._skills[self.getSkillName(skillFile)] = SkillService(self._mqttClient, SkillStore(skillFile))
            self._skills[self.getSkillName(skillFile)].subscribeToMqttTopics()

    def addSkill(self, skill):
        if not self.skillExists(skill):
            self._skills[skill.lower()] = SkillService(self._mqttClient, SkillStore(skill + ".db"))
        else:
            raise ValueError(f"Skill {skill} already exists.")
        return self._skills[skill]

    def skillExists(self, skillName):
        return skillName.lower() in self.listSkills()
    
    def getSkillName(self, skillPath):
        return skillPath[:-3].lower()
    
    def listSkills(self):
        return map(lambda x: self.getSkillName(x), os.listdir("skills/"))

    def removeSkill(self, skillName):
        del self._skills[skillName.lower()]
        os.remove("skills/" + skillName + ".db")
        
    def getSkill(self, skillName):
        return self._skills[skillName.lower()]
    
    def getSkills(self):
        return self._skills

