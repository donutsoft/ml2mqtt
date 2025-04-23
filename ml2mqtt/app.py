from Config import Config
from MqttClient import MqttClient
from flask import Flask, render_template, request, url_for, redirect, abort, Response
from SkillManager import SkillManager
from io import StringIO

import json
import logging
import os
from typing import Callable, Optional, Any

logging.basicConfig(level=logging.INFO)
logStream = StringIO()
streamHandler = logging.StreamHandler(logStream)
streamHandler.setLevel(logging.INFO)
streamHandler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logger = logging.getLogger("ml2mqtt")
logger.setLevel(logging.INFO)
logger.addHandler(streamHandler)

os.makedirs("skills", exist_ok=True)

class IngressMiddleware:
    def __init__(self, app: Callable) -> None:
        self.app = app

    def __call__(self, environ: dict[str, Any], start_response: Callable) -> Any:
        ingress_path = environ.get("HTTP_X_INGRESS_PATH")
        if ingress_path:
            environ["SCRIPT_NAME"] = ingress_path
        return self.app(environ, start_response)

app = Flask(__name__, static_url_path='')
app.wsgi_app = IngressMiddleware(app.wsgi_app)

config = Config()
mqttClient = MqttClient(config.getValue("mqtt"))
skillManager = SkillManager(mqttClient)

@app.route("/")
def home() -> str:
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
def checkModel() -> str:
    model_name = request.args.get("name", "").strip().lower()
    slug = slugify(model_name)
    is_taken = skillManager.skillExists(slug)
    return json.dumps({"exists": is_taken})

def slugify(name: str) -> str:
    return ''.join(c if c.isalnum() else '-' for c in name.lower()).strip('-')

@app.route("/create-model", methods=["GET", "POST"])
def createModel() -> Response:
    if request.method == "POST":
        modelName = request.form.get("model_name")
        defaultValue = request.form.get("default_value")
        mqttTopic = request.form.get("mqtt_topic")

        newModel = skillManager.addSkill(modelName)
        newModel.setMqttTopic(mqttTopic)
        newModel.setDefaultValue("*", defaultValue)
        newModel.setName(modelName)
        newModel.subscribeToMqttTopics()

        return redirect(url_for("home"))

    return render_template("create-model.html", title="Add Model", active_page="create_model")

@app.route("/delete-model/<string:modelName>", methods=["POST"])
def deleteModel(modelName: str) -> Response:
    skillManager.removeSkill(modelName)
    return redirect(url_for("home"))

@app.route("/logs")
def logs() -> str:
    return render_template("logs.html", logs=logs, active_page="logs")

@app.route("/logs/raw")
def logsRaw() -> str:
    logLines = logStream.getvalue().splitlines()
    return render_template("logs_raw.html", logs=logLines)

@app.route("/edit-model/<string:modelName>/<section>")
def editModel(modelName: str, section: str = "settings") -> str:
    validSections = ["settings", "observations", "preprocessors", "postprocessors"]

    if section not in validSections:
        abort(404)

    model = {"name": modelName}

    if section == "observations":
        model["observations"] = skillManager.getSkill(modelName).getObservations()
        model["labels"] = skillManager.getSkill(modelName).getLabels()
    elif section == "settings":
        model["params"] = {}

    sectionTemplate = f"edit_model/{section}.html"

    return render_template(
        "edit_model.html",
        title=f"Edit Model: {model['name']}",
        activePage=None,
        activeSection=section,
        model=model,
        sectionTemplate=sectionTemplate
    )

@app.route("/edit-model/<string:modelName>/settings/update")
def updateModelSettings(modelName: str) -> str:
    return json.dumps({"success": True})

@app.route("/edit-model/<string:modelName>/settings/autotune")
def autoTuneModel(modelName: str) -> str:
    return json.dumps({"success": True})

@app.route("/edit-model/<string:modelName>/settings/test")
def testModel(modelName: str) -> str:
    return json.dumps({"success": True})

@app.route("/api/model/<int:modelId>/observation/<int:observationId>/explicit", methods=["POST"])
def updateExplicitMatch(modelId: int, observationId: int) -> str:
    data = request.get_json()
    isExplicit = data.get("explicitMatch", False)
    return json.dumps({"success": True})

@app.route("/api/model/<int:modelId>/observation/<int:observationId>/delete", methods=["POST"])
def apiDeleteObservation(modelId: int, observationId: int) -> str:
    return json.dumps({"success": True})