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
        self._X_test: Optional[pd.DataFrame] = None
        self._y_test: Optional[np.ndarray] = None
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
            self._X_test = X_test
            self._y_test = y_test

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


    def getFeatureImportance(self) -> Optional[Dict[str, float]]:
        """
        Returns a dictionary mapping feature names to their importance scores.
        If the model is not trained, returns None.
        """
        if not self._modelTrained or self._rf_model is None:
            self.logger.warning("Model is not trained. Feature importances unavailable.")
            return None

        try:
            featureImportances = self._rf_model.feature_importances_
            featureNames = self._rf_model.feature_names_in_
            return dict(zip(featureNames, featureImportances))
        except AttributeError:
            self.logger.error("Unable to retrieve feature importances.")
            return None
        
    def getAccuracy(self) -> Optional[float]:
        """
        Returns the accuracy score of the model using the last training/test split.
        If the model was not trained successfully, returns None.
        """
        if not self._modelTrained or self._rf_model is None:
            self.logger.warning("Model is not trained. Accuracy unavailable.")
            return None

        try:
            X_test = self._X_test
            y_test = self._y_test
            y_pred = self._rf_model.predict(X_test)
            return accuracy_score(y_test, y_pred)
        except AttributeError:
            self.logger.error("Test data unavailable. Cannot compute accuracy.")
            return None