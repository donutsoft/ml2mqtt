from Config import Config
from MqttClient import MqttClient
from flask import Flask, render_template, request, url_for, redirect, abort, Response
from SkillManager import SkillManager
from io import StringIO

import json
import logging
import math
import os
from typing import Callable, Any, cast, Dict, Protocol, TypedDict, List
from SkillStore import SkillObservation, SensorKey

logging.basicConfig(level=logging.INFO)
logStream = StringIO()
streamHandler = logging.StreamHandler(logStream)
streamHandler.setLevel(logging.INFO)
streamHandler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logger = logging.getLogger("ml2mqtt")
logger.setLevel(logging.INFO)
logger.addHandler(streamHandler)

os.makedirs("skills", exist_ok=True)

class WSGIApp(Protocol):
    def __call__(self, environ: Dict[str, Any], start_response: Callable) -> Any: ...

class IngressMiddleware:
    def __init__(self, app: WSGIApp) -> None:
        self.app = app

    def __call__(self, environ: Dict[str, Any], start_response: Callable) -> Any:
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

        if modelName is None:
            abort(400, "Missing model name")
        if mqttTopic is None:
            abort(400, "Missing MQTT topic")

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
    validSections = ["settings", "entities", "observations",  "preprocessors", "postprocessors", "mqtt"]

    if section not in validSections:
        logger.error(f"Invalid section: {section} not found in {validSections}")
        abort(404)

    class ViewModel(TypedDict):
        name: str
        params: Dict[str, Any]
        observations: List[SkillObservation]
        entities: List[SensorKey]
        labels: List[str]
        currentPage: int
        totalPages: int

    model: ViewModel = {"name": modelName, "params": {}, "observations": [], "labels": [], "currentPage": 0, "totalPages": 0}

    if section == "observations":
        page = int(request.args.get("page", 1))
        pageSize = 50
        allObservations = skillManager.getSkill(modelName).getObservations()
        total = len(allObservations)

        start = (page - 1) * pageSize
        end = start + pageSize
        paginated = allObservations[start:end]

        model["observations"] = paginated
        model["currentPage"] = page
        model["labels"] = skillManager.getSkill(modelName).getLabels()
        model["totalPages"] = math.ceil(total / pageSize)

    elif section == "settings":
        logger.info(f"Label stats {skillManager.getSkill(modelName).getLabelStats()}")
        model["params"] = { 
            "accuracy": skillManager.getSkill(modelName).getAccuracy(),
            "observationCount": len(skillManager.getSkill(modelName).getObservations()),
            "modelSize": skillManager.getSkill(modelName).getModelSize(),
            "n_estimators": 0,
            "max_depth": 0,
            "labelStats": skillManager.getSkill(modelName).getLabelStats()
        }
    elif section == "entities":
        model["entities"] = skillManager.getSkill(modelName).getSensorKeys()
    elif section == "mqtt":
        model["params"] = {
            "mqttTopic": skillManager.getSkill(modelName).getMqttTopic(),
        }

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
    if data is None:
        abort(400, "Missing or invalid JSON payload")

    isExplicit = data.get("explicitMatch", False)
    return json.dumps({"success": True})

@app.route("/api/model/<int:modelId>/observation/<int:observationId>/delete", methods=["POST"])
def apiDeleteObservation(modelId: int, observationId: int) -> str:
    return json.dumps({"success": True})