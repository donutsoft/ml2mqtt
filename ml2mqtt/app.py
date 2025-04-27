from Config import Config
from MqttClient import MqttClient
from flask import Flask
from ModelManager import ModelManager
from io import StringIO
import logging
import os

from routes.model_routes import init_model_routes
from routes.log_routes import init_log_routes

# Setup logging
logging.basicConfig(level=logging.INFO)
logStream = StringIO()
streamHandler = logging.StreamHandler(logStream)
streamHandler.setLevel(logging.INFO)
streamHandler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logger = logging.getLogger("ml2mqtt")
logger.setLevel(logging.INFO)
logger.addHandler(streamHandler)

# Create models directory if it doesn't exist
os.makedirs("models", exist_ok=True)

app = Flask(__name__, static_url_path='')
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