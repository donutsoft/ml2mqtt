from Config import Config
from MqttClient import MqttClient
from flask import Flask, render_template, request, url_for, redirect

from SkillManager import SkillManager
from io import StringIO

import json
import logging

logging.basicConfig(level=logging.INFO)
logStream = StringIO()
streamHandler = logging.StreamHandler(logStream)
streamHandler.setLevel(logging.INFO)
streamHandler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logger = logging.getLogger("ml2mqtt")
logger.setLevel(logging.INFO)
logger.addHandler(streamHandler)


app = Flask(__name__)
config = Config()
mqttClient = MqttClient(config.getValue("mqtt"))
skillManager = SkillManager(mqttClient)

@app.route("/")
def home():
    skills = []
    skillMap = skillManager.getSkills()
    for skill in skillMap:
        skillName = skillMap[skill].getName()
        skills.append({
            "name": skillName,
            "mqtt_topic": skillMap[skill].getMqttTopic()
        })
    return render_template("home.html", title="Home", active_page="home", skills=skills)

@app.route("/check-skill-name")
def checkSkill():
    skill_name = request.args.get("name", "").strip().lower()
    slug = slugify(skill_name)
    is_taken = skillManager.skillExists(skill_name)
    return json.dumps({"exists": is_taken})

def slugify(name):
    return ''.join(c if c.isalnum() else '-' for c in name.lower()).strip('-')

@app.route("/create-skill", methods=["GET", "POST"])
def createSkill():
    if request.method == "POST":
        skillName = request.form.get("skill_name")
        defaultValue = request.form.get("default_value")
        mqttTopic = request.form.get("mqtt_topic")

        newSkill = skillManager.addSkill(skillName)
        newSkill.setMqttTopic(mqttTopic)
        newSkill.setDefaultValue("*", defaultValue)
        newSkill.setName(skillName)
        newSkill.subscribeToMqttTopics()

        return redirect(url_for("home"))  # Or wherever you want to go next

    return render_template("create-skill.html", title="Add Skill", active_page="create_skill")

@app.route("/delete-skill/<string:skillName>", methods=["POST"])
def deleteSkill(skillName):
    skillManager.removeSkill(skillName)
    return redirect(url_for("home"))

@app.route("/edit-skill", methods=["GET", "POST"])
def editSkill():
    pass

@app.route("/logs")
def logs():
    return render_template("logs.html", logs=logs, active_page="logs")

@app.route("/logs/raw")
def logsRaw():
    logLines = logStream.getvalue().splitlines()
    return render_template("logs_raw.html", logs=logLines)


#database = Database("test_skill")
#database.addObservation("test_label", { "basement": 123, "livingroom": 456 })
#database.addObservation("test_label", { "basement": 726 })
#database.addObservation("test_label", { "basement": 700, "bedroom": 326 })

#for obs in database.getObservations():
 #   print(obs)

