import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder, OrdinalEncoder
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import train_test_split, GridSearchCV, RandomizedSearchCV
from sklearn.metrics import accuracy_score, classification_report
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
import logging
from typing import TypedDict, Optional, List, Dict, Any, Union
from ModelStore import ModelObservation


class KNNParams(TypedDict):
    n_neighbors: int
    weights: str  # 'uniform' or 'distance'
    p: int        # 1 = Manhattan, 2 = Euclidean


DEFAULT_KNN_PARAMS: KNNParams = {
    "n_neighbors": 5,
    "weights": "uniform",
    "p": 2
}


class KNNClassifier:
    def __init__(self, params: Optional[KNNParams] = None):
        self.params: KNNParams = {**DEFAULT_KNN_PARAMS, **(params or {})}

        self.logger: logging.Logger = logging.getLogger(__name__)
        self.logger.info(f"KNNClassifier initialized with params: {self.params}")
        self._X_test: Optional[pd.DataFrame] = None
        self._y_test: Optional[np.ndarray] = None
        self._pipeline: Optional[Pipeline] = None
        self.labelEncoder: LabelEncoder = LabelEncoder()
        self._modelTrained: bool = False
        self._categoricalCols: List[str] = []

    def populateDataframe(self, observations: List[ModelObservation]) -> None:
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

        self._categoricalCols = X.select_dtypes(include=["object", "category"]).columns.tolist()
        numericalCols = X.select_dtypes(include=[np.number]).columns.tolist()

        preprocessor = ColumnTransformer([
            ('cat', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1), self._categoricalCols),
            ('num', 'passthrough', numericalCols)
        ])

        self._pipeline = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('classifier', KNeighborsClassifier(**self.params))
        ])

        try:
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3)
            self._pipeline.fit(X_train, y_train)
            self._X_test = X_test
            self._y_test = y_test
            self._modelTrained = True
        except ValueError as e:
            self.logger.info(f"Not enough data to train the model: {e}")
            self._modelTrained = False

    def predictLabel(self, sensorValues: Dict[str, Any]) -> Optional[str]:
        if not self._pipeline or not self._modelTrained:
            return None

        X = pd.DataFrame([sensorValues])
        X = X.reindex(columns=self._X_test.columns, fill_value=None)

        try:
            y_pred = self._pipeline.predict(X)
            return self.labelEncoder.inverse_transform(y_pred)[0]
        except Exception as e:
            self.logger.error(f"Prediction failed: {e}")
            return None

    def getFeatureImportance(self) -> Optional[Dict[str, float]]:
        self.logger.info("KNN does not provide feature importances.")
        return None

    def getAccuracy(self) -> Optional[float]:
        if not self._modelTrained or self._pipeline is None:
            self.logger.warning("Model is not trained. Accuracy unavailable.")
            return None

        try:
            y_pred = self._pipeline.predict(self._X_test)
            return accuracy_score(self._y_test, y_pred)
        except Exception as e:
            self.logger.error(f"Accuracy calculation failed: {e}")
            return None

    def getLabelStats(self) -> Optional[Dict[str, Any]]:
        if not self._modelTrained or self._pipeline is None:
            return None

        try:
            y_pred = self._pipeline.predict(self._X_test)
            report = classification_report(
                self._y_test,
                y_pred,
                labels=np.arange(len(self.labelEncoder.classes_)),
                target_names=self.labelEncoder.classes_,
                output_dict=True,
                zero_division=0
            )

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

    def optimizeParameters(self, observations: List[ModelObservation]) -> Dict[str, Any]:
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

        self._categoricalCols = X.select_dtypes(include=["object", "category"]).columns.tolist()
        numericalCols = X.select_dtypes(include=[np.number]).columns.tolist()

        preprocessor = ColumnTransformer([
            ('cat', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1), self._categoricalCols),
            ('num', 'passthrough', numericalCols)
        ])

        X_trainval, X_test_final, y_trainval, y_test_final = train_test_split(X, y, test_size=0.3, random_state=42)

        paramGrid = {
            "classifier__n_neighbors": list(range(1, 31)),
            "classifier__weights": ["uniform", "distance"],
            "classifier__p": [1, 2]
        }

        try:
            pipeline = Pipeline([
                ('preprocessor', preprocessor),
                ('classifier', KNeighborsClassifier())
            ])

            search = RandomizedSearchCV(
                estimator=pipeline,
                param_distributions=paramGrid,
                n_iter=20,
                scoring='accuracy',
                cv=3,
                n_jobs=-1,
                random_state=42,
                verbose=1,
                refit=True
            )

            search.fit(X_trainval, y_trainval)
            bestParamsFull = search.best_params_
            bestParams = {
                k.replace('classifier__', ''): v
                for k, v in bestParamsFull.items()
            }

            self.logger.info(f"Best KNN parameters: {bestParams}")
            self.params = bestParams

            finalAccuracy = accuracy_score(y_test_final, search.best_estimator_.predict(X_test_final))
            self.logger.info(f"Final accuracy on held-out test set: {round(finalAccuracy, 4)}")

            self._pipeline = search.best_estimator_
            self._X_test = X_test_final
            self._y_test = y_test_final
            self._modelTrained = True

            return bestParams

        except Exception as e:
            self.logger.error(f"Hyperparameter optimization failed: {e}")
            return {}

    def getModelParameters(self) -> KNNParams:
        return self.params