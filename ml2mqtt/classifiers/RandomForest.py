import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
from sklearn.tree import export_graphviz
import logging

from typing import Optional, List, Dict, Any
from SkillStore import SkillObservation
from sklearn.metrics import classification_report
import random

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
        
    def getLabelStats(self) -> Optional[Dict[str, Any]]:
        if not self._modelTrained or self._rf_model is None:
            return None

        try:
            y_pred = self._rf_model.predict(self._X_test)
            report = classification_report(
                self._y_test,
                y_pred,
                labels=np.arange(len(self.labelEncoder.classes_)),
                target_names=self.labelEncoder.classes_,
                output_dict=True
            )

            # Filter only the labels, exclude 'accuracy', 'macro avg', etc.
            return {
                label: {
                    "support": int(stats["support"]),
                    "precision": round(stats["precision"], 3),
                    "recall": round(stats["recall"], 3),
                    "f1": round(stats["f1-score"], 3),
                }
                for label, stats in report.items()
                if label in self.labelEncoder.classes_
            }
        except Exception as e:
            self.logger.error(f"Label stats generation failed: {e}")
            return None

    def optimizeParameters(self, observations: List[SkillObservation]) -> Dict[str, Any]:
        """
        Performs two-stage hyperparameter tuning:
        1. RandomizedSearchCV for broad exploration
        2. GridSearchCV for fine-tuned refinement around best candidate
        Returns the best parameter set found.
        """
        data: List[Dict[str, Any]] = []
        labels: List[str] = []

        for observation in observations:
            data.append(observation.sensorValues)
            labels.append(observation.label)

        if not data or not labels:
            self.logger.warning("No data available for optimization.")
            return {}

        X = pd.DataFrame.from_records(data)
        y = self.labelEncoder.fit_transform(labels)

        try:
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3)

            # --- Stage 1: Randomized Search
            randomGrid = {
                'n_estimators': list(range(50, 201, 25)),
                'max_depth': [None] + list(range(10, 41, 10)),
                'min_samples_split': [2, 5, 10],
                'min_samples_leaf': [1, 2, 4],
                'max_features': ['sqrt', 'log2'],
                'bootstrap': [True, False]
            }

            rf = RandomForestClassifier()
            randomSearch = RandomizedSearchCV(
                estimator=rf,
                param_distributions=randomGrid,
                n_iter=30,
                scoring='accuracy',
                cv=3,
                n_jobs=-1,
                random_state=42,
                verbose=1
            )

            randomSearch.fit(X_train, y_train)
            bestRandomParams = randomSearch.best_params_
            self.logger.info(f"Stage 1 best parameters: {bestRandomParams}")

            # --- Stage 2: Refined Grid around best
            def expandRange(val, step, minimum=1):
                if isinstance(val, int):
                    return sorted(set([
                        max(val - step, minimum),
                        val,
                        val + step
                    ]))
                return [val]

            refinedGrid = {
                'n_estimators': expandRange(bestRandomParams['n_estimators'], 50, minimum=10),
                'max_depth': expandRange(bestRandomParams['max_depth'], 10, minimum=1) if bestRandomParams['max_depth'] else [None],
                'min_samples_split': expandRange(bestRandomParams['min_samples_split'], 2, minimum=2),
                'min_samples_leaf': expandRange(bestRandomParams['min_samples_leaf'], 1, minimum=1),
                'max_features': [bestRandomParams['max_features']],
                'bootstrap': [bestRandomParams['bootstrap']]
            }

            gridSearch = GridSearchCV(
                estimator=RandomForestClassifier(),
                param_grid=refinedGrid,
                scoring='accuracy',
                cv=5,
                n_jobs=-1,
                verbose=1
            )

            gridSearch.fit(X_train, y_train)
            bestParams = gridSearch.best_params_

            self._rf_model = gridSearch.best_estimator_
            self._X_test = X_test
            self._y_test = y_test
            self._modelTrained = True

            self.logger.info(f"Stage 2 refined best parameters: {bestParams}")
            return bestParams

        except Exception as e:
            self.logger.error(f"Hyperparameter optimization failed: {e}")
            return {}