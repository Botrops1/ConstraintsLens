"""Build a release ZIP from the tag whose version Fusion will display."""
import argparse
import json
from pathlib import Path
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="existing release tag, e.g. v1.6.6")
    args = parser.parse_args()
    if not re.fullmatch(r"v[0-9]+(?:\.[0-9]+){2}", args.tag):
        parser.error("expected a vX.Y.Z tag")
    root = Path(__file__).resolve().parents[1]
    ref = f"refs/tags/{args.tag}"
    commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", ref + "^{commit}"], cwd=root, text=True
    ).strip()
    manifest = subprocess.check_output(
        ["git", "show", f"{commit}:ConstraintLens/ConstraintLens.manifest"], cwd=root
    )
    version = json.loads(manifest)["version"]
    if args.tag != f"v{version}":
        parser.error(f"{args.tag} contains manifest version {version}; check the tagged commit")
    archive = Path(f"ConstraintLens-{args.tag}.zip")
    subprocess.run(
        ["git", "archive", "--format=zip", "-9", "-o", archive.resolve(), commit, "ConstraintLens"],
        cwd=root, check=True,
    )
    print(archive)


if __name__ == "__main__":
    main()
