import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder, OrdinalEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, GridSearchCV, RandomizedSearchCV
from sklearn.metrics import accuracy_score, classification_report
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from typing import TypedDict, Optional, List, Dict, Any, Union
import logging
from ModelStore import ModelObservation


class RandomForestParams(TypedDict):
    n_estimators: int
    max_depth: Optional[int]
    min_samples_split: int
    min_samples_leaf: int
    max_features: Union[str, None]
    class_weight: Union[str, None]
    bootstrap: bool
    oob_score: bool


DEFAULT_RANDOM_FOREST_PARAMS: RandomForestParams = {
    "n_estimators": 100,
    "max_depth": None,
    "min_samples_split": 2,
    "min_samples_leaf": 1,
    "max_features": "sqrt",
    "class_weight": None,
    "bootstrap": True,
    "oob_score": False
}


class RandomForest:
    def __init__(self, params: Optional[RandomForestParams] = None):
        self.params: RandomForestParams = {**DEFAULT_RANDOM_FOREST_PARAMS, **(params or {})}
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.logger.info(f"RandomForest initialized with params: {self.params}")

        self.labelEncoder: LabelEncoder = LabelEncoder()
        self._pipeline: Optional[Pipeline] = None
        self._X_test: Optional[pd.DataFrame] = None
        self._y_test: Optional[np.ndarray] = None
        self._modelTrained: bool = False
        self._categoricalCols: List[str] = []

    def populateDataframe(self, observations: List[ModelObservation]) -> None:
        data: List[Dict[str, Any]] = []
        labels: List[str] = []

        for obs in observations:
            data.append(obs.sensorValues)
            labels.append(obs.label)

        if not data or not labels:
            self.logger.warning("No data available for training.")
            self._modelTrained = False
            return

        X = pd.DataFrame(data)
        y = self.labelEncoder.fit_transform(labels)

        self._categoricalCols = X.select_dtypes(include=["object", "category"]).columns.tolist()
        numericalCols = X.select_dtypes(include=[np.number]).columns.tolist()

        preprocessor = ColumnTransformer(
            transformers=[
                ('cat', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1), self._categoricalCols),
                ('num', 'passthrough', numericalCols)
            ]
        )

        self._pipeline = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('classifier', RandomForestClassifier(**self.params))
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
            y_prob = self._pipeline.predict_proba(X)
            label = self.labelEncoder.inverse_transform(y_pred)[0]
            confidence = max(y_prob[0])  # Confidence level as the probability of the predicted label
            return label, confidence
        except Exception as e:
            self.logger.error(f"Prediction failed: {e}")
            return None

    def getFeatureImportance(self) -> Optional[Dict[str, float]]:
        if not self._modelTrained or self._pipeline is None:
            return None

        try:
            clf = self._pipeline.named_steps["classifier"]
            featureNames = self._X_test.columns
            importances = clf.feature_importances_
            return dict(zip(featureNames, importances))
        except Exception as e:
            self.logger.error(f"Feature importances retrieval failed: {e}")
            return None

    def getAccuracy(self) -> Optional[float]:
        if not self._modelTrained or self._pipeline is None:
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

        for obs in observations:
            data.append(obs.sensorValues)
            labels.append(obs.label)

        if not data or not labels:
            self.logger.warning("No data available for optimization.")
            return {}

        X = pd.DataFrame(data)
        y = self.labelEncoder.fit_transform(labels)

        self._categoricalCols = X.select_dtypes(include=["object", "category"]).columns.tolist()
        numericalCols = X.select_dtypes(include=[np.number]).columns.tolist()

        preprocessor = ColumnTransformer(
            transformers=[
                ('cat', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1), self._categoricalCols),
                ('num', 'passthrough', numericalCols)
            ]
        )

        X_trainval, X_test_final, y_trainval, y_test_final = train_test_split(X, y, test_size=0.3, random_state=42)

        baseGrid = {
            'n_estimators': list(range(50, 501, 25)),
            'max_depth': [None] + list(range(1, 41, 10)),
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4],
            'max_features': ['sqrt', 'log2', None],
            'class_weight': [None, 'balanced', 'balanced_subsample'],
        }

        bootstrapGrid = {**baseGrid, 'bootstrap': [True], 'oob_score': [True, False]}
        noBootstrapGrid = {**baseGrid, 'bootstrap': [False]}

        def runSearch(param_grid):
            pipeline = Pipeline([
                ('preprocessor', preprocessor),
                ('classifier', RandomForestClassifier())
            ])
            search = RandomizedSearchCV(
                estimator=pipeline,
                param_distributions={'classifier__' + k: v for k, v in param_grid.items()},
                n_iter=30,
                scoring='accuracy',
                cv=3,
                random_state=42,
                n_jobs=-1,
                verbose=1,
                refit=True
            )
            search.fit(X_trainval, y_trainval)
            return search

        search1 = runSearch(bootstrapGrid)
        search2 = runSearch(noBootstrapGrid)
        bestSearch = search1 if search1.best_score_ >= search2.best_score_ else search2
        bestRandomParams = {
            k.replace('classifier__', ''): v
            for k, v in bestSearch.best_params_.items()
        }
        self.logger.info(f"Stage 1 best parameters: {bestRandomParams}")

        def expandRange(val, step, minimum=1):
            if isinstance(val, int):
                return sorted(set([max(val - step, minimum), val, val + step]))
            return [val]

        refinedGrid = {
            'n_estimators': expandRange(bestRandomParams['n_estimators'], 50, 10),
            'max_depth': expandRange(bestRandomParams['max_depth'], 10, 1) if bestRandomParams['max_depth'] else [None],
            'min_samples_split': expandRange(bestRandomParams['min_samples_split'], 2, 2),
            'min_samples_leaf': expandRange(bestRandomParams['min_samples_leaf'], 1, 1),
            'max_features': [bestRandomParams['max_features']],
            'class_weight': [bestRandomParams['class_weight']],
            'bootstrap': [bestRandomParams['bootstrap']],
        }
        if bestRandomParams['bootstrap']:
            refinedGrid['oob_score'] = [bestRandomParams.get('oob_score', False)]

        gridSearch = GridSearchCV(
            Pipeline([
                ('preprocessor', preprocessor),
                ('classifier', RandomForestClassifier())
            ]),
            param_grid={'classifier__' + k: v for k, v in refinedGrid.items()},
            scoring='accuracy',
            cv=5,
            n_jobs=-1,
            verbose=1
        )
        gridSearch.fit(X_trainval, y_trainval)
        bestParams = {
            k.replace('classifier__', ''): v
            for k, v in gridSearch.best_params_.items()
        }

        self.logger.info(f"Stage 2 best parameters: {bestParams}")
        self.params = bestParams

        self._pipeline = gridSearch.best_estimator_
        self._X_test = X_test_final
        self._y_test = y_test_final
        self._modelTrained = True

        finalAccuracy = accuracy_score(y_test_final, self._pipeline.predict(X_test_final))
        self.logger.info(f"Final accuracy on held-out test set: {round(finalAccuracy, 4)}")

        return bestParams

    def getModelParameters(self) -> RandomForestParams:
        return self.params
