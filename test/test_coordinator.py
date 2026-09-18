import unittest
import json
import os
import sys
from custom_components.moscow_transport.coordinator import MoscowTransportCoordinator


class MockEntry:
    def __init__(self, stop_id, routes=None, scan_interval=60):
        self.data = {"stop_id": stop_id, "routes": routes or []}
        self.options = {}


class CoordinatorProcessingTest(unittest.TestCase):
    def setUp(self):
        fixture_path = os.path.join(sys.path[0], "test", "response_fixture.json")
        if not os.path.exists(fixture_path):
            fixture_path = os.path.join(sys.path[0], "response_fixture.json")
        with open(fixture_path, encoding="utf-8") as f:
            self.fixture = json.load(f)

    def test_process_stop_data_all_routes(self):
        entry = MockEntry("test-uuid", routes=[])
        # Instantiate coordinator without HA hass (bypassing __init__)
        coord = object.__new__(MoscowTransportCoordinator)
        coord.entry = entry
        coord.stop_id = "test-uuid"

        data = coord._process_stop_data(self.fixture)
        self.assertEqual(data["stop_id"], "test-uuid")
        self.assertEqual(data["stop_name"], self.fixture["name"])
        self.assertIn("688", data["routes"])
        self.assertIn("733", data["routes"])
        self.assertTrue(len(data["all_arrivals"]) > 0)
        # Verify sorted arrivals
        for i in range(len(data["all_arrivals"]) - 1):
            self.assertLessEqual(
                data["all_arrivals"][i]["time_seconds"],
                data["all_arrivals"][i + 1]["time_seconds"],
            )

    def test_process_stop_data_filtered_routes(self):
        entry = MockEntry("test-uuid", routes=["688"])
        coord = object.__new__(MoscowTransportCoordinator)
        coord.entry = entry
        coord.stop_id = "test-uuid"

        data = coord._process_stop_data(self.fixture)
        self.assertIn("688", data["routes"])
        self.assertNotIn("733", data["routes"])
        for item in data["all_arrivals"]:
            self.assertEqual(item["route"], "688")


if __name__ == "__main__":
    unittest.main()
