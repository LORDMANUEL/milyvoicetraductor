from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PUBLISHER = ROOT / ".github/workflows/publish-stable-2.0.2.yml"


class StablePublisherContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = PUBLISHER.read_text(encoding="utf-8")

    def test_stable_release_assets_are_never_clobbered(self) -> None:
        self.assertNotIn(
            'gh release edit "$RELEASE_TAG"',
            self.source,
            "Una versión estable publicada no debe editarse automáticamente.",
        )
        self.assertNotIn(
            'gh release upload "$RELEASE_TAG" release/* --repo "$REPOSITORY" --clobber',
            self.source,
            "Los assets de una versión estable son inmutables y no deben sobrescribirse.",
        )

    def test_existing_release_must_match_verified_sha_and_checksums(self) -> None:
        for marker in (
            "targetCommitish",
            'test "$existing_target" = "$VERIFIED_SHA"',
            'gh release download "$RELEASE_TAG"',
            "sha256sum -c SHA256SUMS.txt",
            "cmp release/SHA256SUMS.txt existing-release/SHA256SUMS.txt",
        ):
            self.assertIn(marker, self.source)

    def test_new_release_is_created_from_exact_verified_sha(self) -> None:
        self.assertIn("head_branch == 'stable/2.0.x'", self.source)
        self.assertIn('ARTIFACT_NAME: MilyVoiceTraductor-Full-2.0.2-Windows-x64-${{ github.event.workflow_run.head_sha }}', self.source)
        self.assertIn('--target "$VERIFIED_SHA"', self.source)


if __name__ == "__main__":
    unittest.main()
