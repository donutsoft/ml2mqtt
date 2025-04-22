import unittest
from RandomForest import RandomForest

class TestRandomForest(unittest.TestCase):
    def test_simple_prediction(self):
        rf = RandomForest()
        observations = [
            {"label": "test_label3", "sensorValues": {"basement": 700, "livingroom": 326}},
            {"label": "test_label1", "sensorValues": {"basement": 123, "livingroom": 456}},
            {"label": "test_label1", "sensorValues": {"basement": 123, "livingroom": 456}},
            {"label": "test_label1", "sensorValues": {"basement": 123, "livingroom": 456}},
            {"label": "test_label3", "sensorValues": {"basement": 700, "livingroom": 326}},
        ]
        rf.populateDataframe(observations)
        prediction = rf.predictLabel({"basement": 123, "livingroom": 456})
        self.assertEqual(prediction, "test_label1")
        


if __name__ == '__main__':
    unittest.main()