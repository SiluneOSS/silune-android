#!/usr/bin/env python3
"""Exercise the upstream guard against night mode regressions."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("night_guard", Path(__file__).with_name("check-night-mode.py"))
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
ROOT = Path(__file__).resolve().parents[1]


def fixture(root):
    for relative in guard.SOURCE_HASHES.keys() | guard.REQUIRED.keys():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((ROOT / relative).read_text())


class NightModeGuardTest(unittest.TestCase):
    def test_current_feature_passes(self):
        self.assertEqual([], guard.check(ROOT))

    def test_removal_of_each_integration_fails(self):
        for relative in guard.SOURCE_HASHES.keys() | guard.REQUIRED.keys():
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                fixture(root)
                (root / relative).unlink()
                self.assertTrue(guard.check(root))

    def test_changed_compressor_pcm_policy_saved_setting_and_tv_toggle_fail(self):
        mutations = [
            (guard.COMMON + "player/audio/AudioNormalizationEffect.kt", "MBC_RATIO = 4f", "MBC_RATIO = 1f"),
            (guard.COMMON + "player/audio/AudioNormalizationController.kt", "preferredTunneling && !enabled", "preferredTunneling"),
            (guard.COMMON + "settings/AndroidPlayerSettingsStore.kt",
             "writeBoolLocal(AUDIO_NORMALIZATION_ENABLED, value)", "writeBool(AUDIO_NORMALIZATION_ENABLED, value)"),
            (guard.TV + "ui/screens/player/TvPlayerHud.kt",
             "onActivate = { onAudioNormalizationChanged(!audioNormalizationEnabled) }", "onActivate = {}"),
        ]
        for relative, old, new in mutations:
            with self.subTest(change=old), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                fixture(root)
                path = root / relative
                original = path.read_text()
                self.assertIn(old, original)
                path.write_text(original.replace(old, new))
                self.assertTrue(guard.check(root))

    def test_formatting_and_comment_changes_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            for relative in guard.SOURCE_HASHES:
                path = root / relative
                path.write_text("// Review note\n" + path.read_text().replace("    ", "  "))
            self.assertEqual([], guard.check(root))


if __name__ == "__main__":
    unittest.main()
