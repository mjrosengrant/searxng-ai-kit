import json
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from rich.console import Console
from typer.testing import CliRunner

import searxng_cli
from searxng_cli import make_json_safe, json_serial


class AnswerLike:
    def as_dict(self):
        return {
            "answer": "OpenAI answer text",
            "engine": "duckduckgo",
        }


class ResultLike:
    def __init__(self):
        self.fields = {
            "title": "OpenAI",
            "url": "https://openai.com/",
            "content": "AI research and products",
            "engine": "duckduckgo",
            "parsed_url": object(),
            "engines": {"duckduckgo", "brave"},
        }

    def __iter__(self):
        return iter(self.fields)

    def __getitem__(self, key):
        return self.fields[key]

    def as_dict(self):
        return self.fields


class JsonSerialTests(unittest.TestCase):
    def test_make_json_safe_preserves_paper_publication_metadata(self):
        from searx.result_types import Paper

        published = datetime(2026, 11, 9, 12, 34, 56, tzinfo=timezone.utc)
        paper = Paper(
            title="Research paper",
            url="https://example.org/paper?signature=AbC%2F123",
            publishedDate=published,
        )

        safe_value = make_json_safe(paper)

        self.assertEqual(safe_value["publishedDate"], published.isoformat())
        self.assertEqual(
            safe_value["date_of_publication"],
            {"datetime": published.isoformat()},
        )
        self.assertEqual(json.loads(json.dumps(safe_value))["url"], paper.url)

    def test_json_serial_converts_nested_date_time_structures(self):
        from searx.weather import DateTime

        published = datetime(2026, 11, 9, 12, 34, 56, tzinfo=timezone.utc)
        payload = {"metadata": {"published": DateTime(published)}}

        encoded = json.dumps(payload, default=json_serial)

        self.assertEqual(
            json.loads(encoded),
            {"metadata": {"published": {"datetime": published.isoformat()}}},
        )

    def test_serializes_searxng_result_objects_with_as_dict(self):
        payload = {"answers": [AnswerLike()]}

        encoded = json.dumps(payload, default=json_serial)

        self.assertEqual(
            json.loads(encoded),
            {
                "answers": [
                    {
                        "answer": "OpenAI answer text",
                        "engine": "duckduckgo",
                    }
                ]
            },
        )

    def test_make_json_safe_converts_typed_result_rows(self):
        result = ResultLike()

        safe_value = make_json_safe(result)

        self.assertEqual(
            safe_value,
            {
                "title": "OpenAI",
                "url": "https://openai.com/",
                "content": "AI research and products",
                "engine": "duckduckgo",
                "engines": ["brave", "duckduckgo"],
            },
        )

    def test_json_serial_converts_typed_result_rows(self):
        payload = {"results": [ResultLike()]}

        encoded = json.dumps(payload, default=json_serial)

        self.assertEqual(
            json.loads(encoded),
            {
                "results": [
                    {
                        "title": "OpenAI",
                        "url": "https://openai.com/",
                        "content": "AI research and products",
                        "engine": "duckduckgo",
                        "engines": ["brave", "duckduckgo"],
                    }
                ]
            },
        )


class CliJsonOutputTests(unittest.TestCase):
    def test_fetch_json_preserves_long_urls_and_content(self):
        first_url = "https://example.org/Paper?signature=" + "AbC%2FDeF%2BGHi%3D" * 20
        second_url = "https://example.org/Other?token=" + "XyZ%2b123" * 20
        for urls in ([first_url], [first_url, second_url]):
            with self.subTest(url_count=len(urls)):
                payload = [
                    {"success": True, "url": url, "title": "研究 paper",
                     "content": "Long source text with [brackets]. " * 30}
                    for url in urls
                ]
                with (
                    patch.object(searxng_cli, "fetch_url_content", AsyncMock(return_value=payload[0])),
                    patch.object(searxng_cli, "fetch_multiple_urls_async", AsyncMock(return_value=payload)),
                    patch.object(searxng_cli, "console", Console(width=40, color_system=None)),
                ):
                    result = CliRunner().invoke(
                        searxng_cli.app, ["fetch-urls", *urls, "--format", "json"],
                    )

                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(json.loads(result.stdout), payload)

    def test_fetch_human_output_remains_available(self):
        payload = {"success": True, "url": "https://example.org/paper",
                   "title": "Research paper", "content": "Source text"}
        with patch.object(searxng_cli, "fetch_url_content", AsyncMock(return_value=payload)):
            result = CliRunner().invoke(
                searxng_cli.app, ["fetch-urls", payload["url"], "--format", "human"],
            )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(payload["title"], result.stdout)
        self.assertIn(payload["content"], result.stdout)


if __name__ == "__main__":
    unittest.main()
