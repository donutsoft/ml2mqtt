from flask import Blueprint, render_template, request, url_for, redirect, abort, Response, jsonify
from typing import Dict, Any, List, Optional
import json
import math
from ModelStore import ModelObservation, EntityKey
from classifiers.RandomForest import RandomForestParams
from classifiers.KNNClassifier import KNNParams
from utils.helpers import slugify

model_bp = Blueprint('model', __name__)

def init_model_routes(model_manager):
    @model_bp.route("/")
    def home() -> str:
        models = []
        modelMap = model_manager.getModels()
        for model in modelMap:
            modelName = modelMap[model].getName()
            models.append({
                "name": modelName,
                "mqtt_topic": modelMap[model].getMqttTopic()
            })
        return render_template("home.html", title="Home", active_page="home", models=models, mqtt_connected=model_manager._mqttClient._connected)

    @model_bp.route("/check-model-name")
    def checkModel() -> str:
        model_name = request.args.get("name", "").strip().lower()
        slug = slugify(model_name)
        is_taken = model_manager.modelExists(slug)
        return json.dumps({"exists": is_taken})

    @model_bp.route("/create-model", methods=["GET", "POST"])
    def createModel() -> Response:
        if request.method == "POST":
            modelName = request.form.get("model_name")
            defaultValue = request.form.get("default_value")
            mqttTopic = request.form.get("mqtt_topic")

            if modelName is None:
                abort(400, "Missing model name")
            if mqttTopic is None:
                abort(400, "Missing MQTT topic")

            newModel = model_manager.addModel(modelName)
            newModel.setMqttTopic(mqttTopic)
            newModel.setDefaultValue("*", defaultValue)
            newModel.setName(modelName)
            newModel.subscribeToMqttTopics()

            return redirect(url_for("model.home"))

        return render_template("create-model.html", title="Add Model", active_page="create_model")

    @model_bp.route("/delete-model/<string:modelName>/", methods=["POST"])
    def deleteModel(modelName: str) -> Response:
        model_manager.removeModel(modelName)
        return redirect(url_for("model.home"))

    @model_bp.route("/edit-model/<string:modelName>/<section>")
    def editModel(modelName: str, section: str = "settings") -> str:
        validSections = ["settings", "entities", "observations", "preprocessors", "postprocessors", "mqtt"]

        if section not in validSections:
            abort(404)

        class ViewModel:
            def __init__(self):
                self.name: str = modelName
                self.params: Dict[str, Any] = {}
                self.observations: List[ModelObservation] = []
                self.entities: List[EntityKey] = []
                self.labels: List[str] = []
                self.currentPage: int = 0
                self.totalPages: int = 0

        model = ViewModel()

        if section == "observations":
            page = int(request.args.get("page", 1))
            pageSize = 50
            allObservations = model_manager.getModel(modelName).getObservations()
            total = len(allObservations)

            start = (page - 1) * pageSize
            end = start + pageSize
            paginated = allObservations[start:end]

            model.observations = paginated
            model.currentPage = page
            model.labels = model_manager.getModel(modelName).getLabels()
            model.totalPages = math.ceil(total / pageSize)

        elif section == "settings":
            model.params = { 
                "accuracy": model_manager.getModel(modelName).getAccuracy(),
                "observationCount": len(model_manager.getModel(modelName).getObservations()),
                "modelSize": model_manager.getModel(modelName).getModelSize(),
                "modelParameters": model_manager.getModel(modelName).getModelSettings(),
                "labelStats": model_manager.getModel(modelName).getLabelStats()
            }
        elif section == "entities":
            model.entities = model_manager.getModel(modelName).getEntityKeys()
        elif section == "mqtt":
            model.params = {
                "mqttTopic": model_manager.getModel(modelName).getMqttTopic(),
            }

        sectionTemplate = f"edit_model/{section}.html"

        return render_template(
            "edit_model.html",
            title=f"Edit Model: {model.name}",
            activePage=None,
            activeSection=section,
            model=model,
            sectionTemplate=sectionTemplate
        )

    @model_bp.route("/edit-model/<string:modelName>/settings/update", methods=["POST"])
    def updateModelSettings(modelName: str) -> str:
        def get_int(name: str, default: Optional[int] = None) -> Optional[int]:
            val = request.form.get(name)
            return int(val) if val and val.isdigit() else default

        def get_optional_int(name: str) -> Optional[int]:
            val = request.form.get(name)
            return int(val) if val and val.isdigit() else None

        def get_bool(name: str) -> bool:
            return request.form.get(name) in ["true", "on", "1"]

        def get_str_or_none(name: str) -> Optional[str]:
            val = request.form.get(name)
            return val if val not in ["None", "", None] else None

        try:
            modelType = request.form.get("modelType", "RandomForest")

            settings: Dict[str, Any] = {
                "model_type": modelType,
                "model_parameters": {}
            }

            if modelType == "RandomForest":
                rfParams: RandomForestParams = {
                    "n_estimators": get_int("nEstimators", 100),
                    "max_depth": get_optional_int("maxDepth"),
                    "min_samples_split": get_int("minSamplesSplit", 2),
                    "min_samples_leaf": get_int("minSamplesLeaf", 1),
                    "max_features": get_str_or_none("maxFeatures"),
                    "class_weight": get_str_or_none("classWeight"),
                    "bootstrap": get_bool("bootstrap"),
                    "oob_score": get_bool("oobScore"),
                }
                settings["model_parameters"]["RandomForest"] = rfParams

            elif modelType == "KNN":
                knnParams: KNNParams = {
                    "n_neighbors": get_int("nNeighbors", 5),
                    "weights": request.form.get("weights", "uniform"),
                    "metric": request.form.get("metric", "minkowski"),
                }
                settings["model_parameters"]["KNN"] = knnParams

            else:
                return jsonify(success=False, error=f"Unknown model type '{modelType}'"), 400

            model_manager.getModel(modelName).setModelSettings(settings)
            return jsonify(success=True)

        except Exception as e:
            return jsonify(success=False, error=str(e)), 400

    @model_bp.route("/edit-model/<string:modelName>/settings/autotune", methods=["POST"])
    def autoTuneModel(modelName: str) -> str:
        model_manager.getModel(modelName).optimizeParameters()
        return json.dumps({"success": True})

    @model_bp.route("/api/model/<int:modelId>/observation/<int:observationId>/explicit", methods=["POST"])
    def updateExplicitMatch(modelId: int, observationId: int) -> str:
        data = request.get_json()
        if data is None:
            abort(400, "Missing or invalid JSON payload")

        isExplicit = data.get("explicitMatch", False)
        return json.dumps({"success": True})

    @model_bp.route("/api/model/<string:modelName>/observation/<float:observationTime>/delete", methods=["POST"])
    def apiDeleteObservation(modelName: str, observationTime: float) -> str:
        try:
            model_manager.getModel(modelName).deleteObservation(observationTime)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @model_bp.route("/edit-model/<string:modelName>/model-settings/<string:modelType>")
    def getModelSettingsTemplate(modelName: str, modelType: str) -> str:
        if modelType not in ["RandomForest", "KNN"]:
            abort(404)
        model = ViewModel(modelName)
        settings = model_manager.getModel(modelName).getModelSettings()
        
        # Initialize default parameters if they don't exist
        if "model_parameters" not in settings:
            settings["model_parameters"] = {}
        
        if modelType == "KNN":
            if "KNN" not in settings["model_parameters"]:
                settings["model_parameters"]["KNN"] = {
                    "n_neighbors": 5,
                    "weights": "uniform",
                    "metric": "minkowski"
                }
        
        model.params = {
            "modelParameters": {
                "model_type": modelType,
                "model_parameters": settings["model_parameters"]
            }
        }
        return render_template(f"edit_model/partials/model_settings/{modelType.lower()}.html", model=model)

    @model_bp.route("/api/model/<string:modelName>/entity/<string:entityName>/delete", methods=["POST"])
    def deleteEntity(modelName: str, entityName: str) -> Response:
        try:
            model_manager.getModel(modelName).deleteEntity(entityName)
            return jsonify({"success": True})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": "Internal server error"}), 500

    @model_bp.route("/delete-label/<string:modelName>/<string:label>", methods=["POST"])
    def deleteLabel(modelName: str, label: str) -> Response:
        try:
            model_manager.getModel(modelName).deleteObservationsByLabel(label)
            return redirect(url_for("model.editModel", modelName=modelName, section="settings"))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @model_bp.route("/edit-model/<string:modelName>/postprocessor/add", methods=["POST"])
    def addPostprocessor(modelName: str) -> Response:
        try:
            data = request.get_json()
            if data is None:
                return jsonify({"error": "Missing or invalid JSON payload"}), 400
                
            model_manager.getModel(modelName).addPostprocessor(data)
            return jsonify({"success": True})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": "Internal server error"}), 500

    @model_bp.route("/edit-model/<string:modelName>/postprocessor/delete", methods=["POST"])
    def deletePostprocessor(modelName: str) -> Response:
        try:
            data = request.get_json()
            if data is None or "index" not in data:
                return jsonify({"error": "Missing index in payload"}), 400
                
            model_manager.getModel(modelName).removePostprocessor(data["index"])
            return jsonify({"success": True})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": "Internal server error"}), 500

    @model_bp.route("/edit-model/<string:modelName>/postprocessor/reorder", methods=["POST"])
    def reorderPostprocessors(modelName: str) -> Response:
        try:
            data = request.get_json()
            if data is None or "fromIndex" not in data or "toIndex" not in data:
                return jsonify({"error": "Missing fromIndex or toIndex in payload"}), 400
                
            model_manager.getModel(modelName).reorderPostprocessors(data["fromIndex"], data["toIndex"])
            return jsonify({"success": True})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": "Internal server error"}), 500

    return model_bp 