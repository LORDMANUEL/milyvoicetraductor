from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STABLE_PUBLISHER = ROOT / ".github/workflows/publish-stable-2.0.2.yml"
BETA_PUBLISHER = ROOT / ".github/workflows/publish-rc.yml"


def main() -> int:
    failures: list[str] = []

    stable = STABLE_PUBLISHER.read_text(encoding="utf-8")
    stable_required = (
        "head_branch == 'stable/2.0.x'",
        "ARTIFACT_NAME: MilyVoiceTraductor-Full-2.0.2-Windows-x64-${{ github.event.workflow_run.head_sha }}",
        "RELEASE_TAG: v2.0.2",
        "--target \"$VERIFIED_SHA\"",
        "sha256sum -c SHA256SUMS.txt",
        "targetCommitish",
        "cmp release/SHA256SUMS.txt existing-release/SHA256SUMS.txt",
    )
    for marker in stable_required:
        if marker not in stable:
            failures.append(f"Falta contrato de publicación estable: {marker}")
    for marker in (
        "gh release edit \"$RELEASE_TAG\"",
        "gh release upload \"$RELEASE_TAG\" release/* --repo \"$REPOSITORY\" --clobber",
    ):
        if marker in stable:
            failures.append(f"La release estable no puede sobrescribirse: {marker}")

    beta = BETA_PUBLISHER.read_text(encoding="utf-8")
    beta_required = (
        "ARTIFACT_NAME: MilyVoiceTraductor-Certified-2.1.1-Windows-x64-${{ github.event.workflow_run.head_sha }}",
        "RELEASE_TAG: v2.1.1",
        "RELEASE_TITLE: MilyVoiceTraductor 2.1.1 Beta",
        "head_branch == 'main'",
        "test \"$tag_sha\" = \"$VERIFIED_SHA\"",
        "cmp release/SHA256SUMS.txt existing-release/SHA256SUMS.txt",
        "docs/release/RELEASE_NOTES_2.1.1.md",
    )
    for marker in beta_required:
        if marker not in beta:
            failures.append(f"Falta contrato de publicación beta inmutable: {marker}")
    for marker in (
        "RELEASE_TAG: v2.1.0",
        "git tag -f",
        "--force",
        "gh release edit",
        "--clobber",
        "ZhEsLiteBench",
    ):
        if marker in beta:
            failures.append(f"La beta 2.1.1 no puede mutar historia ni publicar evidencia experimental: {marker}")

    if failures:
        print("RELEASE PUBLISHER IMMUTABILITY FAILED")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("RELEASE PUBLISHER IMMUTABILITY OK: 2.0.2 estable y 2.1.1 beta son releases inmutables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
