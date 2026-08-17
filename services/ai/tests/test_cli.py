import tempfile
import unittest
from pathlib import Path

from mily_ai.cli import build_parser


class CliTests(unittest.TestCase):
    def test_model_paths_are_accepted_before_model_subcommand(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            parser = build_parser()
            args = parser.parse_args([
                "models",
                "--data-dir", str(base / "data"),
                "--config-dir", str(base / "config"),
                "--cache-dir", str(base / "cache"),
                "--models-dir", str(base / "models"),
                "install", "business-qwen",
            ])
            self.assertEqual(args.command, "models")
            self.assertEqual(args.model_action, "install")
            self.assertEqual(args.pack_id, "business-qwen")


if __name__ == "__main__":
    unittest.main()
