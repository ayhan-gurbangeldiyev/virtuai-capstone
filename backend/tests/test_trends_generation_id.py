import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from routes.trends import TrendGenerateRequest, generate_from_trend


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, supabase, table_name):
        self.supabase = supabase
        self.table_name = table_name
        self._filters = {}
        self._insert_payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self._filters[key] = value
        return self

    def insert(self, payload):
        self._insert_payload = payload
        return self

    def execute(self):
        if self.table_name == "trends":
            trend_id = self._filters.get("id")
            if trend_id == "trend-1":
                return _FakeResult([
                    {
                        "id": "trend-1",
                        "topic": "AI agent orchestration",
                        "category": "AI",
                        "summary": "Agent orchestration pattern yükseliyor",
                        "keywords": ["agent", "orchestration"],
                    }
                ])
            return _FakeResult([])

        if self.table_name == "generations":
            self.supabase.last_generation_insert = self._insert_payload
            account_id = (self._insert_payload or {}).get("account_id")
            if not account_id:
                raise Exception("null value in column account_id violates not-null constraint")
            return _FakeResult([{"id": "gen-test-1"}])

        return _FakeResult([])


class _FakeSupabase:
    def __init__(self):
        self.last_generation_insert = None

    def table(self, name):
        return _FakeTable(self, name)


class TrendsGenerationIdTests(unittest.IsolatedAsyncioTestCase):
    async def test_trend_generate_persists_account_id_and_returns_generation_id(self):
        fake_supabase = _FakeSupabase()

        async def _fake_generate_with_openai(_system_prompt, _user_prompt, _variants):
            return (["Kısa trend içeriği"], 123)

        fake_server_module = types.ModuleType("server")
        fake_server_module.generate_with_openai = _fake_generate_with_openai

        with patch("routes.trends.get_supabase", return_value=fake_supabase), patch.dict(sys.modules, {"server": fake_server_module}):
            response = await generate_from_trend(
                "trend-1",
                TrendGenerateRequest(platform="twitter", language="tr"),
                _=None,
                user=SimpleNamespace(id="user-1"),
                account_id="acc-1",
            )

        self.assertTrue(response.success)
        self.assertEqual(response.generation_id, "gen-test-1")
        self.assertEqual(fake_supabase.last_generation_insert["account_id"], "acc-1")


if __name__ == "__main__":
    unittest.main()
