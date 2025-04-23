from pathlib import Path
from typing import Dict, List, Iterable
from paho.mqtt.client import Client as MqttClient
from SkillService import SkillService
from SkillStore import SkillStore


class SkillManager:
    def __init__(self, mqttClient: MqttClient, skillsDir: str = "skills/"):
        self._mqttClient: MqttClient = mqttClient
        self._skills: Dict[str, SkillService] = {}
        self._skillsDir: Path = Path(skillsDir)

        try:
            for skillFile in self._skillsDir.glob("*.db"):
                skillName = self.getSkillName(skillFile)
                service = SkillService(self._mqttClient, SkillStore(str(skillFile)))
                self._skills[skillName] = service
                service.subscribeToMqttTopics()
        except FileNotFoundError:
            pass

    def addSkill(self, skill: str) -> SkillService:
        key = skill.lower()
        if key in self._skills:
            raise ValueError(f"Skill '{skill}' already exists.")

        dbPath = self._skillsDir / f"{key}.db"
        service = SkillService(self._mqttClient, SkillStore(str(dbPath)))
        self._skills[key] = service
        return service

    def skillExists(self, skillName: str) -> bool:
        return skillName.lower() in self._skills

    def getSkillName(self, skillPath: Path) -> str:
        return skillPath.stem.lower()

    def listSkills(self) -> List[str]:
        return [self.getSkillName(f) for f in self._skillsDir.glob("*.db")]

    def removeSkill(self, skillName: str) -> None:
        key = skillName.lower()
        if key in self._skills:
            self._skills[key].dispose()
            del self._skills[key]

        try:
            dbPath = self._skillsDir / f"{key}.db"
            dbPath.unlink()
        except FileNotFoundError:
            pass

    def getSkill(self, skillName: str) -> SkillService:
        key = skillName.lower()
        return self._skills[key]

    def getSkills(self) -> Dict[str, SkillService]:
        return self._skills

    def __contains__(self, skillName: str) -> bool:
        return self.skillExists(skillName)

    def __getitem__(self, skillName: str) -> SkillService:
        return self.getSkill(skillName)