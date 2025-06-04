from Config import Config
from MqttClient import MqttClient
from flask import Flask, send_file, abort
from ModelManager import ModelManager
from io import StringIO
import logging
import os
from pathlib import Path
from datetime import datetime, timezone
from routes.model_routes import init_model_routes
from routes.log_routes import init_log_routes

# Setup logging
logging.basicConfig(level=logging.INFO)
logStream = StringIO()
streamHandler = logging.StreamHandler(logStream)
streamHandler.setLevel(logging.INFO)

class ExcludeEndpointFilter(logging.Filter):
    def filter(self, record):
        # Exclude logs that contain specific endpoint
        excludedEndpoints = ['/logs/raw', '/styles/', '/images/']
        for endpoint in excludedEndpoints:
            if endpoint in record.getMessage():
                return False
        return True

class UTCFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')  # ISO 8601 UTC

class IngressMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        ingress_path = environ.get("HTTP_X_INGRESS_PATH")
        if ingress_path:
            environ["SCRIPT_NAME"] = ingress_path
        return self.app(environ, start_response)


streamHandler.setFormatter(UTCFormatter('%(asctime)s - %(levelname)s - %(message)s'))

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(streamHandler)
# Apply the filter
for handler in logging.getLogger().handlers:
    handler.addFilter(ExcludeEndpointFilter())


app = Flask(__name__, static_url_path='')
app.wsgi_app = IngressMiddleware(app.wsgi_app)

@app.context_processor
def inject_globals():
    return dict(
        enumerate=enumerate,
        len=len,
        str=str,
        int=int,
        float=float,
        zip=zip,
        sorted=sorted,
        list=list,
        dict=dict,
        min=min,
        max=max
    )
# Initialize configuration and services
config = Config()

mqttClient = MqttClient(config.getValue("mqtt"))
modelManager = ModelManager(mqttClient, config.getDataPath() + "/models")

# Register blueprints
app.register_blueprint(init_model_routes(modelManager))
app.register_blueprint(init_log_routes(logStream))

@app.route('/download_model_db/<model_slug>')
def download_model_db(model_slug: str):
    data_path = config.getDataPath()
    # Ensure model_slug is safe to use as a file name component (basic check)
    if not model_slug or ".." in model_slug or "/" in model_slug:
        abort(400, description="Invalid model slug.")

    db_file_name = model_slug + ".db"
    db_file_path = Path(data_path) / "models" / db_file_name

    if not db_file_path.is_file():
        abort(404, description="Database file not found.")

    return send_file(
        db_file_path,
        as_attachment=True,
        download_name=db_file_name
    )