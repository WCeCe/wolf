"""llm.retry 传输层重试与 json_schema 不可用检测。"""
import unittest
from unittest.mock import patch

from openai import APIConnectionError, APIStatusError

from llm.retry import (
    call_with_transport_retries,
    is_response_format_unavailable,
    is_retryable_transport_error,
)


class TestRetryHelpers(unittest.TestCase):
    def test_response_format_unavailable_from_message(self) -> None:
        exc = Exception(
            "Error code: 400 - {'error': {'message': "
            "'This response_format type is unavailable now'}}"
        )
        self.assertTrue(is_response_format_unavailable(exc))

    def test_response_format_unavailable_400_status(self) -> None:
        exc = APIStatusError(
            "Error code: 400 - invalid json_schema response_format",
            response=unittest.mock.MagicMock(status_code=400),
            body=None,
        )
        self.assertTrue(is_response_format_unavailable(exc))

    def test_connection_error_is_retryable(self) -> None:
        req = unittest.mock.MagicMock()
        self.assertTrue(
            is_retryable_transport_error(APIConnectionError(request=req))
        )
        self.assertTrue(is_retryable_transport_error(Exception("Connection error.")))

    def test_400_generic_not_retryable_unless_transport(self) -> None:
        exc = APIStatusError(
            "bad",
            response=unittest.mock.MagicMock(status_code=400),
            body=None,
        )
        exc.message = "invalid model"
        self.assertFalse(is_retryable_transport_error(exc))


class TestCallWithTransportRetries(unittest.TestCase):
    @patch("llm.retry.sleep_before_transport_retry")
    def test_succeeds_on_second_attempt(self, _sleep: unittest.mock.MagicMock) -> None:
        calls = {"n": 0}

        def flaky() -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                raise APIConnectionError(request=unittest.mock.MagicMock())
            return "ok"

        self.assertEqual(
            call_with_transport_retries(flaky, label="test"),
            "ok",
        )
        self.assertEqual(calls["n"], 2)

    @patch("llm.retry.sleep_before_transport_retry")
    def test_raises_after_max_attempts(self, _sleep: unittest.mock.MagicMock) -> None:
        def always_fail() -> str:
            raise APIConnectionError(request=unittest.mock.MagicMock())

        with self.assertRaises(APIConnectionError):
            call_with_transport_retries(always_fail, label="test")

    def test_response_format_unavailable_not_retried(self) -> None:
        calls = {"n": 0}

        def bad_format() -> str:
            calls["n"] += 1
            raise Exception("This response_format type is unavailable now")

        with self.assertRaises(Exception):
            call_with_transport_retries(bad_format, label="test")
        self.assertEqual(calls["n"], 1)


if __name__ == "__main__":
    unittest.main()
