from Config import Config
from MqttClient import MqttClient
from flask import Flask, render_template, request, url_for, redirect, abort, Response, jsonify
from SkillManager import SkillManager
from io import StringIO

import json
import logging
import math
import os
from typing import Callable, Any, cast, Dict, Protocol, TypedDict, List, Optional
from SkillStore import SkillObservation, SensorKey
from classifiers.RandomForest import RandomForestParams

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
            "modelParameters": skillManager.getSkill(modelName).getModelParameters(),
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

@app.route("/edit-model/<string:modelName>/settings/update", methods=["POST"])
def updateModelSettings(modelName: str) -> str:
    def get_int(name: str, default: Optional[int] = None) -> Optional[int]:
        val = request.form.get(name)
        return int(val) if val and val.isdigit() else default

    def get_optional_int(name: str) -> Optional[int]:
        val = request.form.get(name)
        return int(val) if val and val.isdigit() else None

    def get_bool(name: str) -> bool:
        return request.form.get(name) == "true"

    def get_str_or_none(name: str) -> Optional[str]:
        val = request.form.get(name)
        return val if val not in ["None", "", None] else None

    try:
        modelParams: RandomForestParams = {
            "n_estimators": get_int("nEstimators", 100),
            "max_depth": get_optional_int("maxDepth"),
            "min_samples_split": get_int("minSamplesSplit", 2),
            "min_samples_leaf": get_int("minSamplesLeaf", 1),
            "max_features": get_str_or_none("maxFeatures"),
            "class_weight": get_str_or_none("classWeight"),
            "bootstrap": get_bool("bootstrap"),
            "oob_score": get_bool("oobScore"),
        }

        # Example: store to DB, update model, etc.
        app.logger.info(f"Received new parameters for model '{modelName}': {modelParams}")
        skillManager.getSkill(modelName).setModelParameters(modelParams)

        return jsonify(success=True)

    except Exception as e:
        app.logger.error(f"Failed to update model settings for {modelName}: {e}")
        return jsonify(success=False, error=str(e)), 400

@app.route("/edit-model/<string:modelName>/settings/autotune", methods=["POST"])
def autoTuneModel(modelName: str) -> str:
    skillManager.getSkill(modelName).optimizeParameters()
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