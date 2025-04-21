import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.model_selection import GridSearchCV
from sklearn.tree import export_graphviz
import logging

class RandomForest:
    def __init__(self):
        self.logger = logging.getLogger("ml2mqtt")
        self._rf_model = None
        self.labelEncoder = LabelEncoder()

    def populateDataframe(self, observations):
        data = []
        labels = []
        for observation in observations:
            label = observation["label"]
            sensorValues = observation["sensorValues"]
            data.append(sensorValues)
            labels.append(label)
        X = pd.DataFrame.from_records(data)
        y = self.labelEncoder.fit_transform(labels)
        try:
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3)
            rf_model = RandomForestClassifier(n_estimators=50)
            rf_model.fit(X_train, y_train)
            self._rf_model = rf_model
        except ValueError:
            self.logger.info("Not enough data to train the model")
            self._modelTrained = False

    def predictLabel(self, sensorValues):
        if self._rf_model == None:
            return None

        X = pd.DataFrame([sensorValues])
        y_pred = self._rf_model.predict(X)
        return self.labelEncoder.inverse_transform(y_pred)[0]