"""Delivery tests run offline with no bot token, network, or backend dependencies."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.scripts.publish_figures import (
    DeliveryUncertain, GitHubLedger, Telegram, TelegramRejected, main,
    message_payload, post_key, publish, shown_posts,
)


def post(number=1, **changes):
    return {"id": "db-id", "url": f"https://t.me/testfigure/{number}",
            "handle": "testfigure", "kind": "analysis", "name_fa": "چهرهٔ آزمایشی",
            "topic_fa": "اقتصاد و جامعه", "summary_fa": "به باور او، این یک دیدگاه است.",
            "published_at": f"2026-10-01T{number:02}:00:00+00:00", **changes}


def export(*posts):
    return {"fields": {}, "figures": [{"name_fa": "چهرهٔ آزمایشی", "posts": list(posts)}]}


class MemoryLedger:
    def __init__(self):
        self.state = None
        self.history = []
        self.fail_after_send = False

    def load(self):
        return copy.deepcopy(self.state)

    def save(self, state):
        if self.fail_after_send and any(e["status"] == "sent" for e in state["posts"].values()):
            raise RuntimeError("State write failed")
        self.state = copy.deepcopy(state)
        self.history.append(copy.deepcopy(state))


class PublisherTests(unittest.TestCase):
    def setUp(self):
        printer = patch("builtins.print")
        printer.start()
        self.addCleanup(printer.stop)
        self.ledger = MemoryLedger()
        self.bot = Mock()
        self.bot.send.side_effect = lambda *args: 101
        self.sleep = Mock()

    def run_posts(self, *posts, **kwargs):
        return publish(shown_posts(export(*posts)), self.ledger, self.bot, -100123,
                       sleep=self.sleep, **kwargs)

    def test_first_run_baselines_the_archive_and_never_posts_it(self):
        self.assertEqual(self.run_posts(post(1), post(2))["baseline"], 2)
        self.assertEqual(self.run_posts(post(1), post(2))["sent"], 0)
        self.bot.send.assert_not_called()

    def test_new_posts_queue_and_only_one_sends_per_run_in_chronological_order(self):
        self.run_posts(post(1))
        self.assertEqual(self.run_posts(post(3), post(1), post(2))["sent"], 1)
        self.assertEqual(self.bot.send.call_args.args[0]["url"], post(2)["url"])
        self.assertEqual(self.ledger.state["posts"][post(3)["url"]]["status"], "pending")
        self.assertEqual(self.run_posts(post(2), post(3))["sent"], 1)
        self.assertEqual([c.args[0]["url"] for c in self.bot.send.call_args_list],
                         [post(2)["url"], post(3)["url"]])
        self.assertEqual(self.run_posts(post(2), post(3))["sent"], 0)
        self.assertEqual(self.bot.send.call_count, 2)
        self.sleep.assert_not_called()
        for key in [post(2)["url"], post(3)["url"]]:
            self.assertTrue(any(h["posts"][key]["status"] == "sending"
                                for h in self.ledger.history if key in h["posts"]))

    def test_db_id_summary_and_url_case_changes_do_not_republish(self):
        self.run_posts(post(1))
        rebuilt = post(1, id="new-db-id", summary_fa="خلاصهٔ اصلاح‌شده",
                       url="https://t.me/TESTFIGURE/1/?single")
        self.assertEqual(self.run_posts(rebuilt)["sent"], 0)
        self.bot.send.assert_not_called()

    def test_export_filters_hidden_content_and_deduplicates_urls(self):
        visible = shown_posts(export(post(1), post(1, id="other"),
                                     post(2, kind="relay"), post(3, kind="promo"),
                                     post(4, summary_fa=""), post(5, kind="party_claim")))
        self.assertEqual([p["url"] for p in visible], [post(1)["url"], post(5)["url"]])

    def test_failure_retains_queue_even_if_post_disappears_from_site(self):
        self.run_posts(post(1))
        self.bot.send.side_effect = TelegramRejected("403")
        with self.assertRaises(TelegramRejected):
            self.run_posts(post(1), post(2))
        self.assertEqual(self.ledger.state["posts"][post(2)["url"]]["status"], "pending")
        self.bot.send.side_effect = lambda *args: 102
        self.assertEqual(self.run_posts(post(1))["sent"], 1)
        self.assertEqual(self.bot.send.call_args.args[0]["url"], post(2)["url"])

    def test_timeout_is_not_replayed_but_other_new_posts_still_send(self):
        self.run_posts(post(1))
        self.bot.send.side_effect = DeliveryUncertain("timeout")
        with self.assertRaises(DeliveryUncertain):
            self.run_posts(post(2))
        self.bot.send.reset_mock(side_effect=True)
        self.bot.send.return_value = 103
        result = self.run_posts(post(2), post(3))
        self.assertEqual(result["uncertain"], 1)
        self.assertEqual(result["sent"], 1)
        self.assertEqual(self.bot.send.call_args.args[0]["url"], post(3)["url"])

    def test_checkpoint_failure_after_send_does_not_replay(self):
        self.run_posts(post(1))
        self.ledger.fail_after_send = True
        with self.assertRaises(RuntimeError):
            self.run_posts(post(2))
        self.ledger.fail_after_send = False
        self.assertEqual(self.run_posts(post(2))["uncertain"], 1)
        self.assertEqual(self.bot.send.call_count, 1)

    def test_manual_recovery_can_mark_sent_without_resending(self):
        self.run_posts(post(1))
        self.bot.send.side_effect = DeliveryUncertain("timeout")
        with self.assertRaises(DeliveryUncertain):
            self.run_posts(post(2))
        self.bot.send.reset_mock(side_effect=True)
        result = self.run_posts(post(2), resolve_url=post(2)["url"], resolution="mark_sent")
        self.assertEqual(result["uncertain"], 0)
        self.bot.send.assert_not_called()

    def test_manual_retry_works_after_post_leaves_site(self):
        self.run_posts(post(1))
        self.bot.send.side_effect = DeliveryUncertain("timeout")
        with self.assertRaises(DeliveryUncertain):
            self.run_posts(post(2))
        self.bot.send.side_effect = lambda *args: 104
        self.assertEqual(self.run_posts(resolve_url=post(2)["url"], resolution="retry")["sent"], 1)

    def test_bad_state_or_changed_channel_does_not_reset_or_send(self):
        self.run_posts(post(1))
        self.ledger.state["chat_id"] = "another channel"
        with self.assertRaises(ValueError):
            self.run_posts(post(2))
        self.bot.send.assert_not_called()
        self.assertEqual(len(self.ledger.history), 1)

    def test_bad_export_or_source_url_is_rejected(self):
        for data in [{}, {"figures": "bad"}, {"figures": [{"posts": None}]}]:
            with self.assertRaises(ValueError):
                shown_posts(data)
        with self.assertRaises(ValueError):
            post_key("https://example.test/post/1")

    def test_long_unicode_message_is_plain_text_and_keeps_links(self):
        p = shown_posts(export(post(1, summary_fa="دیدگاه <b>&_* 🎉 " * 1000)))[0]
        payload = message_payload(p, -100123)
        self.assertLessEqual(len(payload["text"].encode("utf-16-le")) // 2, 4096)
        self.assertNotIn("parse_mode", payload)
        self.assertIn("<b>&_*", payload["text"])
        self.assertIn("#/figure/testfigure", payload["text"])
        self.assertEqual(payload["reply_markup"]["inline_keyboard"][0][0]["url"], post(1)["url"])


class ApiTests(unittest.TestCase):
    @patch("backend.scripts.publish_figures.http_json")
    def test_identity_and_post_permission_are_required(self, request):
        request.side_effect = [
            (200, {"ok": True, "result": {"id": 10, "username": "janekalaam_bot"}}),
            (200, {"ok": True, "result": {"id": -100123, "username": "jane_kalaam", "type": "channel"}}),
            (200, {"ok": True, "result": {"status": "administrator", "can_post_messages": True}}),
        ]
        self.assertEqual(Telegram("fake").verify("janekalaam_bot", "@jane_kalaam"), -100123)
        request.side_effect = None
        request.return_value = (200, {"ok": True, "result": {"username": "other_bot"}})
        with self.assertRaisesRegex(RuntimeError, "does not belong"):
            Telegram("fake").verify("janekalaam_bot", "@jane_kalaam")

    @patch("backend.scripts.publish_figures.http_json")
    def test_no_post_permission_prevents_publishing(self, request):
        request.side_effect = [
            (200, {"ok": True, "result": {"id": 10, "username": "janekalaam_bot"}}),
            (200, {"ok": True, "result": {"id": -100123, "username": "jane_kalaam", "type": "channel"}}),
            (200, {"ok": True, "result": {"status": "administrator", "can_post_messages": False}}),
        ]
        with self.assertRaisesRegex(RuntimeError, "Post Messages"):
            Telegram("fake").verify("janekalaam_bot", "@jane_kalaam")

    @patch("backend.scripts.publish_figures.http_json")
    def test_explicit_rate_limit_can_retry_but_ambiguous_response_cannot(self, request):
        sleep = Mock()
        request.side_effect = [(429, {"ok": False, "error_code": 429, "parameters": {"retry_after": 2}}),
                               (200, {"ok": True, "result": {"message_id": 123}})]
        self.assertEqual(Telegram("fake", sleep=sleep).send(post(1), -100123), 123)
        sleep.assert_called_once_with(3)
        request.side_effect = RuntimeError("Network request failed")
        with self.assertRaises(DeliveryUncertain):
            Telegram("fake").send(post(1), -100123)

    @patch("backend.scripts.publish_figures.http_json")
    def test_ledger_creates_separate_branch_without_changing_main(self, request):
        request.side_effect = [(404, {}), (404, {}),
                               (200, {"object": {"sha": "main-head"}}), (201, {}),
                               (201, {"content": {"sha": "state-sha"}})]
        ledger = GitHubLedger("nimania/jan-kalam", "fake")
        self.assertIsNone(ledger.load())
        ledger.save({"version": 1, "posts": {}})
        self.assertEqual(ledger.sha, "state-sha")
        writes = [c for c in request.call_args_list if c.kwargs.get("method") in {"POST", "PUT"}]
        self.assertEqual(writes[0].kwargs["data"]["ref"], "refs/heads/telegram-state")
        self.assertEqual(writes[1].kwargs["data"]["branch"], "telegram-state")

    @patch("backend.scripts.publish_figures.http_json")
    def test_large_ledger_uses_raw_content_and_retains_file_sha(self, request):
        state = {"version": 1, "posts": {}}
        request.side_effect = [(200, {"sha": "large-sha", "encoding": "none"}), (200, state)]
        ledger = GitHubLedger("nimania/jan-kalam", "fake")
        self.assertEqual(ledger.load(), state)
        self.assertEqual(ledger.sha, "large-sha")

    @patch("backend.scripts.publish_figures.http_json")
    def test_missing_secret_and_dry_run_never_use_network(self, request):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "figures.json"
            path.write_text(json.dumps(export(post(1))), encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True), patch("builtins.print"):
                self.assertEqual(main(["--figures", str(path)]), 0)
                self.assertEqual(main(["--figures", str(path), "--dry-run"]), 0)
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
