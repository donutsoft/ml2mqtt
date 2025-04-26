from Config import Config
from MqttClient import MqttClient
from flask import Flask
from SkillManager import SkillManager
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

# Create skills directory if it doesn't exist
os.makedirs("skills", exist_ok=True)

app = Flask(__name__, static_url_path='')

# Initialize configuration and services
config = Config()
mqttClient = MqttClient(config.getValue("mqtt"))
skillManager = SkillManager(mqttClient)

# Register blueprints
app.register_blueprint(init_model_routes(skillManager))
app.register_blueprint(init_log_routes(logStream))