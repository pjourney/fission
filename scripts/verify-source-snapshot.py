"""Check that the staged sources match every tracked recursive engine/root file."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def git_files(repository, options):
    data = subprocess.check_output(["git", "-C", str(repository), "ls-files", "-z", *options])
    return [path.decode("utf-8") for path in data.split(b"\0") if path]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


root, stage = map(lambda argument: Path(argument).resolve(), sys.argv[1:3])
engine = root / "upstream-src"
engine_files = sorted(set(git_files(engine, ["--recurse-submodules"]) +
                          git_files(engine, ["--others", "--exclude-standard"])))
fission_files = sorted(set(git_files(root, ["--cached", "--others", "--exclude-standard"])))
manifest = {}
failures = []
for repository, destination, paths in [(engine, stage / "upstream-src", engine_files),
                                       (root, stage, fission_files)]:
    for relative in paths:
        original, copied = repository / relative, destination / relative
        if not original.is_file() or not copied.is_file():
            failures.append("Missing source file: " + str(copied))
            continue
        current_hash, copied_hash = digest(original), digest(copied)
        if current_hash != copied_hash:
            failures.append("Source bytes differ: " + str(copied))
        manifest[copied.relative_to(stage).as_posix()] = current_hash
report = {"passed": not failures, "engine_files": len(engine_files),
          "fission_files": len(fission_files), "total_files": len(manifest),
          "failures": failures}
(stage.parent / "source-verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
(stage / "SOURCE_SHA256.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps(report))
raise SystemExit(bool(failures))
