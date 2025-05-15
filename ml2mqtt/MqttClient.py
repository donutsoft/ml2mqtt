from collections import defaultdict
import paho.mqtt.client as mqtt
import logging
import time

class MqttClient:
    def __init__(self, mqttConfig):
        self.logger = logging.getLogger(__name__)
        self._connected = False
        self.topics = {}
        self._mqttClient = mqtt.Client()
        self._mqttClient.username_pw_set(mqttConfig['username'], mqttConfig['password'])
        self._mqttClient.on_connect = self.onConnect
        self._mqttClient.on_message = self.onMessage
        self._mqttClient.on_disconnect = self.onDisconnect
        
        # Try to connect, but don't block if it fails
        try:
            self._mqttClient.connect(mqttConfig['server'], mqttConfig['port'])
            self._mqttClient.loop_start()
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT server: {e}")
            self._connected = False

    def onConnect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            self.logger.info("Connected to MQTT server")
            for topic in self.topics:
                self.logger.info("Subscribing to " + topic)
                self._mqttClient.subscribe(topic)
        else:
            self._connected = False
            self.logger.error(f"Failed to connect to MQTT server with code: {rc}")

    def onDisconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            self.logger.warning(f"Unexpected disconnection from MQTT server (code: {rc})")
            # Try to reconnect
            try:
                self._mqttClient.reconnect()
            except Exception as e:
                self.logger.error(f"Failed to reconnect to MQTT server: {e}")

    def onMessage(self, client, userdata, msg):
        try:
            if msg.topic in self.topics:
                for callback in self.topics[msg.topic]:
                    callback(msg.payload.decode('utf-8'))
        except Exception as e:
            self.logger.exception("Unhandled exception")
            raise
    
    def subscribe(self, topic, callback):
        shouldSubscribe = False
        if not topic in self.topics:
            self.topics[topic] = []
            self.topics[topic].append(callback)
            shouldSubscribe = True
        
        if self._connected and shouldSubscribe:
            self.logger.info("Post Subscribing to topic %s", topic)
            self._mqttClient.subscribe(topic)

    def unsubscribe(self, topic, callback):
        if topic in self.topics:
            if callback in self.topics[topic]:
                self.topics[topic].remove(callback)
                if len(self.topics[topic]) == 0:
                    del self.topics[topic]
                    self._mqttClient.unsubscribe(topic)
                    self.logger.info("Unsubscribed from topic %s", topic)
            else:
                self.logger.warning("Callback not found in topic %s", topic)
        else:
            self.logger.warning("Topic %s not found", topic)

    def publish(self, topic, message):
        if not self._connected:
            self.logger.warning(f"Cannot publish message - MQTT not connected")
            return
        self.logger.info("Sending message %s to topic %s", message, topic)
        self._mqttClient.publish(topic, message)
