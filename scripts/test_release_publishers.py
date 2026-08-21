from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STABLE_PUBLISHER = ROOT / ".github/workflows/publish-stable-2.0.2.yml"


def main() -> int:
    failures: list[str] = []
    source = STABLE_PUBLISHER.read_text(encoding="utf-8")

    required = (
        "head_branch == 'stable/2.0.x'",
        "ARTIFACT_NAME: MilyVoiceTraductor-Full-2.0.2-Windows-x64-${{ github.event.workflow_run.head_sha }}",
        "RELEASE_TAG: v2.0.2",
        "--target \"$VERIFIED_SHA\"",
        "sha256sum -c SHA256SUMS.txt",
        "targetCommitish",
        "cmp release/SHA256SUMS.txt existing-release/SHA256SUMS.txt",
    )
    for marker in required:
        if marker not in source:
            failures.append(f"Falta contrato de publicación estable: {marker}")

    forbidden = (
        "gh release edit \"$RELEASE_TAG\"",
        "gh release upload \"$RELEASE_TAG\" release/* --repo \"$REPOSITORY\" --clobber",
    )
    for marker in forbidden:
        if marker in source:
            failures.append(f"La release estable no puede sobrescribirse: {marker}")

    if failures:
        print("STABLE PUBLISHER IMMUTABILITY FAILED")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("STABLE PUBLISHER IMMUTABILITY OK: v2.0.2 se publica una sola vez y luego se verifica sin clobber.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
