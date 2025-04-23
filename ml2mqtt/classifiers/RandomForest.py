import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.model_selection import GridSearchCV
from sklearn.tree import export_graphviz
import logging

from typing import Optional, List, Dict, Any
from SkillStore import SkillObservation


class RandomForest:
    def __init__(self):
        self.logger: logging.Logger = logging.getLogger("ml2mqtt")
        self._rf_model: Optional[RandomForestClassifier] = None
        self.labelEncoder: LabelEncoder = LabelEncoder()
        self._modelTrained: bool = False

    def populateDataframe(self, observations: List[SkillObservation]) -> None:
        data: List[Dict[str, Any]] = []
        labels: List[str] = []

        for observation in observations:
            data.append(observation.sensorValues)
            labels.append(observation.label)

        if not data or not labels:
            self.logger.warning("No data available for training.")
            self._modelTrained = False
            return

        X = pd.DataFrame.from_records(data)
        y = self.labelEncoder.fit_transform(labels)

        try:
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3)
            rf_model = RandomForestClassifier(n_estimators=50)
            rf_model.fit(X_train, y_train)
            self._rf_model = rf_model
            self._modelTrained = True
        except ValueError:
            self.logger.info("Not enough data to train the model")
            self._modelTrained = False

    def predictLabel(self, sensorValues: Dict[str, Any]) -> Optional[str]:
        if self._rf_model is None:
            return None

        X = pd.DataFrame([sensorValues])
        y_pred = self._rf_model.predict(X)
        return self.labelEncoder.inverse_transform(y_pred)[0]