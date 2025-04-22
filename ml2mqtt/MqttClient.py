from collections import defaultdict
import paho.mqtt.client as mqtt
import logging

class MqttClient:
    def __init__(self, mqttConfig):
        self.logger = logging.getLogger("ml2mqtt")
        self._connected = False
        self.topics = {}
        self._mqttClient = mqtt.Client()
        self._mqttClient.username_pw_set(mqttConfig['username'], mqttConfig['password'])
        self._mqttClient.on_connect = self.onConnect
        self._mqttClient.on_message = self.onMessage
        self._mqttClient.connect(mqttConfig['server'], mqttConfig['port'])
        self._mqttClient.loop_start()

    def onConnect(self, client, userdata, flags, rc):
        self._connected = True
        self.logger.info("Connected to MQTT server")
        for topic in self.topics:
            self.logger.info("Subscribing to " + topic)
            self._mqttClient.subscribe(topic)

    def onMessage(self, client, userdata, msg):
        if msg.topic in self.topics:
            for callback in self.topics[msg.topic]:
                callback(msg.payload.decode('utf-8'))
                    
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
        self.logger.info("Sending message %s to topic %s", message, topic)
        self._mqttClient.publish(topic, message)
