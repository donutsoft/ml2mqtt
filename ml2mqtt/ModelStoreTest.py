import unittest
import os
from SkillStore import SkillStore

class TestSkillStore(unittest.TestCase):
    def setUp(self):
        try:
            os.remove("skills/test_skill.db")
        except FileNotFoundError:
            pass
        self.db = SkillStore("test_skill")

    def test_retrieveSimpleObservation(self):
        self.db.addObservation("test_label1", { "basement": 123, "livingroom": 456 })
        self.db.addObservation("test_label2", { "basement": 726 })
        self.db.addObservation("test_label3", { "basement": 700, "bedroom": 326 })

        observations = self.db.getObservations()
        self.assertEqual(observations, [{
            "label": "test_label1",
            "time": observations[0]["time"],
            "sensorValues": {
                "basement": 123,
                "livingroom": 456,
                "bedroom": 9999
            }
        }, {
            "label": "test_label2",
            "time": observations[1]["time"],
            "sensorValues": {
                "basement": 726,
                "livingroom": 9999,
                "bedroom": 9999
            }
        }, {
            "label": "test_label3",
            "time": observations[2]["time"],
            "sensorValues": {
                "basement": 700,
                "bedroom": 326,
                "livingroom": 9999
            }
        }])

    def retriveStringObservation(self):
        self.db.addObservation("test_label1", { "basement": 123, "location": "home" })
        self.db.addObservation("test_label2", { "basement": 726 })
        observations = self.db.getObservations()
        self.assertEqual(observations, [{
            "label": "test_label1",
            "time": observations[0]["time"],
            "sensorValues": {
                "basement": 123,
                "location": "home",
            }},
            {
            "label": "test_label2",
            "time": observations[1]["time"],
            "sensorValues": {
                "basement": 726,
                "location": "9999",
            }}])
        
    def tearDown(self):
        try:
            os.remove("skills/test_skill.db")
        except FileNotFoundError:
            pass
        self.db._db.close()

if __name__ == '__main__':
    unittest.main()