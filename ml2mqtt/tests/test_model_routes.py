import unittest
import tempfile
import sqlite3
import os
import shutil
from io import BytesIO

# Attempt to import app and related components
# This might need adjustment based on actual app structure
try:
    from ml2mqtt.app import app as flask_app # Assuming app is named flask_app in app.py
    from ml2mqtt.ModelManager import ModelManager
    from ml2mqtt.Config import Config
    from ml2mqtt.utils.helpers import slugify # Needed for model name verification
except ImportError as e:
    # This helps in diagnosing if the path or app structure is different than assumed
    print(f"Error importing app components: {e}. Adjust imports or PYTHONPATH if necessary.")
    # Fallback for basic structure if imports fail, allowing file creation
    flask_app = None
    ModelManager = None
    Config = None
    slugify = lambda x: x


class TestModelRoutes(unittest.TestCase):

    def setUp(self):
        if flask_app is None or ModelManager is None or Config is None:
            self.skipTest("Flask app or core components could not be imported. Skipping integration tests.")

        self.temp_models_dir = tempfile.mkdtemp()
        self.original_models_dir = Config.MODELS_DIR # Save original
        Config.MODELS_DIR = self.temp_models_dir

        flask_app.config['TESTING'] = True
        flask_app.config['WTF_CSRF_ENABLED'] = False

        # This is crucial: The ModelManager instance must be created *after*
        # Config.MODELS_DIR is patched, or it must be reconfigured.
        # If app.py's `model_manager` is initialized at import time, this won't work.
        # Assuming app.py has a structure like:
        # model_manager = None
        # def init_app(app):
        #   global model_manager
        #   model_manager = ModelManager(app.mqtt_client, Config.MODELS_DIR)
        #   from .routes import model_bp # routes use this model_manager
        #   app.register_blueprint(model_bp)
        # This means we need to ensure the app's model_manager is using the temp dir.
        # A common way is to re-initialize it or ensure it's lazy-loaded.
        # For this test, we'll create one and assume routes can access it via flask_app.model_manager

        # If the app has a factory or a way to get the "live" manager, use it.
        # Otherwise, create one and attach it, hoping routes pick it up.
        # This part is highly dependent on app.py's structure.
        # A mock MQTT client might be needed if ModelManager requires it.
        class MockMQTTClient:
            def __init__(self):
                self._connected = False
            def publish(self, topic, payload, retain=False): pass
            def subscribe(self, topic, callback): pass
            def loop_start(self): pass
            def loop_stop(self): pass
            def connect(self, host, port): self._connected = True
            def disconnect(self): self._connected = False

        self.mock_mqtt_client = MockMQTTClient()
        flask_app.model_manager = ModelManager(mqttClient=self.mock_mqtt_client, modelsDir=self.temp_models_dir)
        self.model_manager = flask_app.model_manager

        self.app = flask_app
        self.client = self.app.test_client()

    def tearDown(self):
        # Clean up models created by model_manager to avoid interference
        if hasattr(self, 'model_manager') and self.model_manager:
            for model_name in list(self.model_manager.getModels().keys()): # list() for safe iteration
                try:
                    self.model_manager.removeModel(model_name)
                except Exception as e:
                    print(f"Error removing model {model_name} in tearDown: {e}")

        if hasattr(self, 'temp_models_dir') and os.path.exists(self.temp_models_dir):
            shutil.rmtree(self.temp_models_dir)

        if hasattr(self, 'original_models_dir'):
            Config.MODELS_DIR = self.original_models_dir # Restore original
        if hasattr(self, 'temp_models_dir') and os.path.exists(self.temp_models_dir):
            shutil.rmtree(self.temp_models_dir)

        # Reset any global config changes if necessary
        # This depends on how Config is structured. If it's a simple module with variables:
        # from ml2mqtt import Config as AppConfig
        # AppConfig.MODELS_DIR = original_models_dir_value (would need to save it in setUp)

    def test_get_upload_database_page(self):
        response = self.client.get('/upload-database')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Upload Database", response.data)
        self.assertIn(b"Model Name", response.data)
        self.assertIn(b"MQTT Topic", response.data)
        self.assertIn(b"Database File", response.data)

    def _create_temp_db(self, db_name="test.db", tables_with_rows=None, settings=None):
        """Helper to create a temporary SQLite DB for testing."""
        # tables_with_rows: {"table_name": [("col_name", "col_type"), ...], ...}
        # settings: {"key": "value", ...}

        db_path = os.path.join(self.temp_models_dir, db_name) # Create in temp_models_dir to ensure it's cleaned up if test fails early
                                                              # Or create in a generic temp dir. For file upload, path doesn't matter as much.
                                                              # Let's use a separate temp dir for the source DB.

        source_temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(source_temp_dir, db_name)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        if tables_with_rows:
            for table_name, schema in tables_with_rows.items():
                col_defs = ", ".join([f"{col_name} {col_type}" for col_name, col_type in schema])
                cursor.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({col_defs})")

        if settings:
            cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
            for key, value in settings.items():
                cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))

        conn.commit()
        conn.close()
        return db_path, source_temp_dir


    def test_post_upload_database_success_defaults(self):
        db_filename = "test_defaults.db"
        db_entities = {"entity1": [("col1", "TEXT")], "entity2": [("col_a", "REAL")]}
        db_settings = {"mqtt_path": "db/mqtt/topic"}

        temp_db_path, source_temp_dir = self._create_temp_db(
            db_name=db_filename,
            tables_with_rows=db_entities,
            settings=db_settings
        )

        try:
            with open(temp_db_path, 'rb') as fp:
                data = {
                    'database_file': (fp, db_filename)
                }
                response = self.client.post('/upload-database', data=data, content_type='multipart/form-data')

            self.assertEqual(response.status_code, 302, f"Response data: {response.data.decode()}") # Should redirect

            # Assuming redirect is to editModel page, e.g., /edit-model/test_defaults/settings
            # This requires url_for to work correctly in test context.
            # Or, we can inspect the model_manager directly.

            model_name_expected = os.path.splitext(db_filename)[0]
            model_slug_expected = slugify(model_name_expected)

            self.assertIn(f'/edit-model/{model_slug_expected}/settings', response.location)

            self.assertTrue(self.model_manager.modelExists(model_slug_expected))
            model_service = self.model_manager.getModel(model_slug_expected)

            self.assertEqual(model_service.getName(), model_name_expected.replace('_', ' ').replace('-', ' ')) # Default display name processing
            self.assertEqual(model_service.getMqttTopic(), db_settings["mqtt_path"])

            entity_keys = [ek.name for ek in model_service.store.getEntityKeys()]
            self.assertCountEqual(entity_keys, list(db_entities.keys()))

        finally:
            if os.path.exists(source_temp_dir):
                shutil.rmtree(source_temp_dir)
            # Model itself will be cleaned by tearDown

    def test_post_upload_database_success_with_user_inputs(self):
        db_filename = "test_user_inputs.db"
        # DB content (will be mostly overridden by user inputs)
        db_entities = {"db_entity1": [], "db_entity2": []}
        db_settings = {"mqtt_path": "db/should_be_overridden"}

        temp_db_path, source_temp_dir = self._create_temp_db(
            db_name=db_filename,
            tables_with_rows=db_entities,
            settings=db_settings
        )

        user_model_name = "My Custom Model"
        user_mqtt_topic = "user/custom/topic"
        user_entity_names_str = "UserEntity1\nUserEntity2\n UserEntity3 " # Test stripping and empty lines
        user_entity_names_list = ["UserEntity1", "UserEntity2", "UserEntity3"]

        expected_model_slug = slugify(user_model_name)

        try:
            with open(temp_db_path, 'rb') as fp:
                form_data = {
                    'database_file': (fp, db_filename),
                    'model_name': user_model_name,
                    'mqtt_topic': user_mqtt_topic,
                    'entity_names': user_entity_names_str
                }
                response = self.client.post('/upload-database', data=form_data, content_type='multipart/form-data')

            self.assertEqual(response.status_code, 302, f"Response data: {response.data.decode()}")
            self.assertIn(f'/edit-model/{expected_model_slug}/settings', response.location)

            self.assertTrue(self.model_manager.modelExists(expected_model_slug))
            model_service = self.model_manager.getModel(expected_model_slug)

            self.assertEqual(model_service.getName(), user_model_name)
            self.assertEqual(model_service.getMqttTopic(), user_mqtt_topic)

            entity_keys = [ek.name for ek in model_service.store.getEntityKeys()]
            self.assertCountEqual(entity_keys, user_entity_names_list)

        finally:
            if os.path.exists(source_temp_dir):
                shutil.rmtree(source_temp_dir)
            # Model itself will be cleaned by tearDown

    def test_post_upload_database_no_file(self):
        response = self.client.post('/upload-database', data={}, content_type='multipart/form-data')

        # Expecting the form to be rendered again with an error
        self.assertEqual(response.status_code, 400) # Or 200 if just re-rendering with error message
        self.assertIn(b"No database file selected", response.data) # Check for error message in HTML

    def test_post_upload_database_empty_filename(self):
        data = {
            'database_file': (BytesIO(b"dummy content"), "") # Empty filename
        }
        response = self.client.post('/upload-database', data=data, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"No database file selected", response.data)

    def test_post_upload_database_model_exists(self):
        existing_model_name = "existing_model"
        existing_model_slug = slugify(existing_model_name)

        # 1. Create an existing model
        # Ensure this uses the same model_manager instance the app uses
        self.model_manager.addModel(existing_model_slug)
        # We might need to set its name if addModel only takes slug
        # For this test, just ensuring the slug exists in ModelManager is key.
        # If setName is crucial for the check in the route, then:
        # existing_model_service = self.model_manager.getModel(existing_model_slug)
        # existing_model_service.setName(existing_model_name) # If addModel doesn't set it.

        # 2. Create a dummy SQLite DB
        db_filename = "new_db_for_existing_model.db"
        temp_db_path, source_temp_dir = self._create_temp_db(db_name=db_filename)

        try:
            with open(temp_db_path, 'rb') as fp:
                form_data = {
                    'database_file': (fp, db_filename),
                    'model_name': existing_model_name, # Attempt to use existing name
                }
                response = self.client.post('/upload-database', data=form_data, content_type='multipart/form-data')

            # Expecting the form to be rendered again with an error
            self.assertEqual(response.status_code, 400)
            self.assertIn(f"Model with name '{existing_model_slug}' already exists.".encode('utf-8'), response.data)

        finally:
            if os.path.exists(source_temp_dir):
                shutil.rmtree(source_temp_dir)
            # The existing_model_slug will be cleaned by tearDown's model removal loop.

if __name__ == '__main__':
    unittest.main()
