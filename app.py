from Config import Config
from MqttClient import MqttClient
from flask import Flask, render_template, request, url_for, redirect

from SkillManager import SkillManager
from io import StringIO

import json
import logging
import os

logging.basicConfig(level=logging.INFO)
logStream = StringIO()
streamHandler = logging.StreamHandler(logStream)
streamHandler.setLevel(logging.INFO)
streamHandler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logger = logging.getLogger("ml2mqtt")
logger.setLevel(logging.INFO)
logger.addHandler(streamHandler)

os.mkdir("skills") if not os.path.exists("skills") else None

app = Flask(__name__)
config = Config()
mqttClient = MqttClient(config.getValue("mqtt"))
skillManager = SkillManager(mqttClient)

@app.route("/")
def home():
    models = []
    modelMap = skillManager.getSkills()
    for model in modelMap:
        modelName = modelMap[model].getName()
        models.append({
            "name": modelName,
            "mqtt_topic": modelMap[model].getMqttTopic()
        })
    return render_template("home.html", title="Home", active_page="home", models=models)

@app.route("/check-model-name")
def checkModel():
    model_name = request.args.get("name", "").strip().lower()
    slug = slugify(model_name)
    is_taken = skillManager.skillExists(slug)
    return json.dumps({"exists": is_taken})

def slugify(name):
    return ''.join(c if c.isalnum() else '-' for c in name.lower()).strip('-')

@app.route("/create-model", methods=["GET", "POST"])
def createModel():
    if request.method == "POST":
        modelName = request.form.get("model_name")
        defaultValue = request.form.get("default_value")
        mqttTopic = request.form.get("mqtt_topic")

        newModel = skillManager.addSkill(modelName)
        newModel.setMqttTopic(mqttTopic)
        newModel.setDefaultValue("*", defaultValue)
        newModel.setName(modelName)
        newModel.subscribeToMqttTopics()

        return redirect(url_for("home"))  # Or wherever you want to go next

    return render_template("create-model.html", title="Add Model", active_page="create_model")

@app.route("/delete-model/<string:modelName>", methods=["POST"])
def deleteModel(modelName):
    skillManager.removeSkill(modelName)
    return redirect(url_for("home"))

@app.route("/edit-model", methods=["GET", "POST"])
def editModel():
    pass

@app.route("/logs")
def logs():
    return render_template("logs.html", logs=logs, active_page="logs")

@app.route("/logs/raw")
def logsRaw():
    logLines = logStream.getvalue().splitlines()
    return render_template("logs_raw.html", logs=logLines)