import unittest
import asyncio
import aiohttp
from custom_components.moscow_transport.const import extract_stop_id_from_input
from custom_components.moscow_transport.api import (
    MoscowTransportApiClient,
    InvalidStopId,
)


class ApiAndParserTest(unittest.TestCase):
    """Test URL and UUID parsing logic."""

    def test_extract_pure_uuid(self):
        uuid = "86f6869e-59dc-44a9-8575-3cee948c6f4f"
        self.assertEqual(extract_stop_id_from_input(uuid), uuid)

    def test_extract_uuid_with_spaces_and_uppercase(self):
        uuid = "  86F6869E-59DC-44A9-8575-3CEE948C6F4F \n"
        self.assertEqual(extract_stop_id_from_input(uuid), "86f6869e-59dc-44a9-8575-3cee948c6f4f")

    def test_extract_from_long_url(self):
        url = "https://moscowapp.mos.ru/stop?id=86f6869e-59dc-44a9-8575-3cee948c6f4f"
        self.assertEqual(extract_stop_id_from_input(url), "86f6869e-59dc-44a9-8575-3cee948c6f4f")

    def test_extract_from_text_containing_url(self):
        text = "Вот ссылка на остановку https://moscowtransport.app/stop?id=99a2734d-84ed-4361-8cc2-5cb3e4e778c5 посмотри"
        self.assertEqual(extract_stop_id_from_input(text), "99a2734d-84ed-4361-8cc2-5cb3e4e778c5")

    def test_extract_invalid_input(self):
        self.assertIsNone(extract_stop_id_from_input(""))
        self.assertIsNone(extract_stop_id_from_input("https://moscowapp.mos.ru/something_else"))
        self.assertIsNone(extract_stop_id_from_input("invalid-uuid-12345"))

    def test_async_resolve_short_url(self):
        async def run_async():
            async with aiohttp.ClientSession() as session:
                client = MoscowTransportApiClient(session)
                # Test resolving short sharing URL
                resolved = await client.async_resolve_stop_id("https://moscowapp.mos.ru/l/S0G3Qb")
                self.assertEqual(resolved, "99a2734d-84ed-4361-8cc2-5cb3e4e778c5")

                # Test resolving user's long URL
                user_url = "https://moscowapp.mos.ru/stop?id=86f6869e-59dc-44a9-8575-3cee948c6f4f"
                resolved_user = await client.async_resolve_stop_id(user_url)
                self.assertEqual(resolved_user, "86f6869e-59dc-44a9-8575-3cee948c6f4f")

                # Test live stop fetch
                stop_info = await client.async_get_stop_info("86f6869e-59dc-44a9-8575-3cee948c6f4f")
                self.assertIn("Соколиной Горы", stop_info["name"])
                routes = client.get_available_routes(stop_info)
                self.assertIn("83", routes)

        asyncio.run(run_async())


if __name__ == "__main__":
    unittest.main()
