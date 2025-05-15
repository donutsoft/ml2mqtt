from Config import Config
from MqttClient import MqttClient
from flask import Flask
from ModelManager import ModelManager
from io import StringIO
import logging
import os
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
        return "/logs/raw" not in record.getMessage()

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

# Create models directory if it doesn't exist
os.makedirs("models", exist_ok=True)

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
modelManager = ModelManager(mqttClient)

# Register blueprints
app.register_blueprint(init_model_routes(modelManager))
app.register_blueprint(init_log_routes(logStream))