#!/usr/bin/env python3
"""Extract the unchanged local Lean import closure from a pinned openai/math checkout.

Usage: python3 scripts/extract_upstream.py /path/to/openai-math [--destination DIR]
The checkout must be at UPSTREAM_COMMIT. Every copied byte is checked against its
Git blob before copying. No network requests or package downloads are performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path


UPSTREAM_URL = "https://github.com/openai/math.git"
UPSTREAM_COMMIT = "adc7f1241b42e322a6451854ab7e4b4c146bf78a"
SOLUTION_MODULE = "OAI.MeasureTheory.Falconer.Campaign123PlanarFurstenbergProof"
CHALLENGE_MODULE = "ComparatorChallenges.FalconerAllDimensions"
MATHLIB_COMMIT = "d13f23b723b8a846827a245b89c10fc7d3f11612"
THEOREM = "OAI.Falconer.falconer_distance_conjecture"
# Exact dependency list from mathlib's lake-manifest.json at MATHLIB_COMMIT.
# These same records appear in the pinned openai/math manifest.
MATHLIB_DEPENDENCIES = {
    "plausible": "118aa17ee84656b8bd727fef7c458ee8c833385c",
    "LeanSearchClient": "ddf04cf3949fa556442341e87d47f9f6e6074707",
    "importGraph": "e928b72544873815af278d38681b31c0293588e3",
    "proofwidgets": "106ff4fafc74ef4ac99d81dbf3ab399118f497a5",
    "aesop": "355695d523e41d0554926416cba2a2b3544fbbc9",
    "Qq": "6a489d9af5d0c47e5b259e2e8bcdfc1811b5a259",
    "batteries": "f2effa3d803fda822b1f97b806c47cf2adfbcbc2",
    "Cli": "e92c9f15fdfacc8536f31cfb3b7ad26c3c8cd204",
}


def git(source: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(source), *args])


def without_comments(text: str) -> str:
    """Mask nested Lean comments and string literals, preserving line boundaries."""
    result = list(text)
    i = 0
    depth = 0
    in_string = False
    while i < len(text):
        if depth:
            if text.startswith("/-", i):
                depth += 1
                result[i:i + 2] = "  "
                i += 2
            elif text.startswith("-/", i):
                depth -= 1
                result[i:i + 2] = "  "
                i += 2
            else:
                if text[i] != "\n":
                    result[i] = " "
                i += 1
        elif in_string:
            if text[i] == "\\" and i + 1 < len(text):
                result[i:i + 2] = "  "
                i += 2
            else:
                if text[i] == '"':
                    in_string = False
                if text[i] != "\n":
                    result[i] = " "
                i += 1
        elif text.startswith("/-", i):
            depth = 1
            result[i:i + 2] = "  "
            i += 2
        elif text.startswith("--", i):
            end = text.find("\n", i)
            if end == -1:
                end = len(text)
            result[i:end] = " " * (end - i)
            i = end
        elif text[i] == '"':
            in_string = True
            result[i] = " "
            i += 1
        else:
            i += 1
    return "".join(result)


def imports(data: bytes) -> list[str]:
    """Read the module header; fail on import syntax this extractor cannot parse."""
    text = without_comments(data.decode("utf-8"))
    tokens = text.split()
    result: list[str] = []
    i = 0
    if tokens[:1] == ["prelude"]:
        i += 1
    if tokens[i:i + 1] == ["module"]:
        i += 1
    while i < len(tokens):
        # Lean 4 module headers can attach visibility/meta modifiers to imports.
        start = i
        while i < len(tokens) and tokens[i] in {"public", "private", "meta"}:
            i += 1
        if i >= len(tokens) or tokens[i] != "import":
            i = start
            break
        i += 1
        if i >= len(tokens) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9'.]*", tokens[i]):
            raise ValueError("Unsupported import syntax in module header")
        result.append(tokens[i])
        i += 1
    # A second import after a non-header token is suspicious, not silently omitted.
    if re.search(r"(?m)^\s*(?:(?:public|private|meta)\s+)*import\s", " ".join(tokens[i:])):
        raise ValueError("Import outside the parsed module header")
    return result


def module_path(name: str) -> Path:
    return Path(*name.split(".")).with_suffix(".lean")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="openai/math repository checkout")
    parser.add_argument("--destination", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    source = args.source.resolve()
    destination = args.destination.resolve()
    head = git(source, "rev-parse", "HEAD").decode().strip()
    if head != UPSTREAM_COMMIT:
        raise SystemExit(f"Expected upstream {UPSTREAM_COMMIT}; checkout is {head}")

    blobs: dict[str, str] = {}
    for line in git(source, "ls-tree", "-r", "--full-tree", UPSTREAM_COMMIT, "lean").splitlines():
        metadata, path = line.split(b"\t", 1)
        _mode, object_type, oid = metadata.split()
        if object_type == b"blob":
            blobs[path.decode()] = oid.decode()

    def checked_data(path: Path) -> bytes:
        relative = path.relative_to(source).as_posix()
        data = path.read_bytes()
        blob_hash = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if blobs.get(relative) != blob_hash:
            raise SystemExit(f"Source bytes differ from the pinned upstream Git blob: {relative}")
        return data

    lean_root = source / "lean"
    pending = [SOLUTION_MODULE, CHALLENGE_MODULE]
    local: dict[str, tuple[bytes, list[str]]] = {}
    external: set[str] = set()
    while pending:
        module = pending.pop()
        if module in local:
            continue
        path = lean_root / module_path(module)
        if not path.is_file():
            raise SystemExit(f"Missing local module: {module}")
        data = checked_data(path)
        module_imports = imports(data)
        local[module] = (data, module_imports)
        for dependency in module_imports:
            if (lean_root / module_path(dependency)).is_file():
                pending.append(dependency)
            elif dependency.split(".")[0] in {"Mathlib", "Lean", "Init", "Std"}:
                external.add(dependency)
            else:
                raise SystemExit(f"Unresolved non-core/non-mathlib dependency: {dependency}")

    destination.mkdir(parents=True, exist_ok=True)
    records = []
    for module, (data, module_imports) in sorted(local.items()):
        relative = module_path(module)
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        records.append({
            "path": relative.as_posix(),
            "upstream_path": "lean/" + relative.as_posix(),
            "module": module,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "imports": module_imports,
        })

    support_files = ["ComparatorChallenges/FalconerAllDimensions.json", "lean-toolchain", "LICENSE"]
    for relative in support_files:
        data = checked_data(lean_root / relative)
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        records.append({
            "path": relative,
            "upstream_path": "lean/" + relative,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        })

    config = json.loads(checked_data(lean_root / "ComparatorChallenges/FalconerAllDimensions.json"))
    upstream_lake_manifest = json.loads(checked_data(lean_root / "lake-manifest.json"))
    upstream_packages = {package["name"]: package for package in upstream_lake_manifest["packages"]}
    selected_revisions = {"mathlib": MATHLIB_COMMIT, **MATHLIB_DEPENDENCIES}
    selected_packages = []
    for name, revision in selected_revisions.items():
        package_record = upstream_packages[name]
        if package_record["rev"] != revision:
            raise SystemExit(f"Unexpected upstream dependency revision for {name}")
        selected_packages.append(package_record)
    lake_manifest = {
        "version": upstream_lake_manifest["version"],
        "packagesDir": upstream_lake_manifest["packagesDir"],
        "packages": selected_packages,
        "name": "falconer-all-dimensions",
        "lakeDir": upstream_lake_manifest["lakeDir"],
        "fixedToolchain": upstream_lake_manifest["fixedToolchain"],
    }
    lake_manifest_text = json.dumps(lake_manifest, indent=2) + "\n"
    (destination / "lake-manifest.json").write_text(lake_manifest_text, encoding="utf-8")
    package = f'''# Standalone extraction; Lean source files are unchanged from openai/math.
name = "falconer-all-dimensions"
version = "0.1.0"
defaultTargets = ["OAI"]

[leanOptions]
autoImplicit = false

[[require]]
name = "mathlib"
git = "https://github.com/leanprover-community/mathlib4.git"
rev = "{MATHLIB_COMMIT}"

[[lean_lib]]
name = "OAI"
roots = ["{SOLUTION_MODULE}"]
globs = ["OAI.+"]

[[lean_lib]]
name = "ComparatorChallenges"
roots = ["{CHALLENGE_MODULE}"]
globs = ["ComparatorChallenges.+"]
'''
    (destination / "lakefile.toml").write_text(package, encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "upstream": {"url": UPSTREAM_URL, "commit": UPSTREAM_COMMIT},
        "extraction": {
            "solution_module": SOLUTION_MODULE,
            "challenge_module": CHALLENGE_MODULE,
            "theorem": THEOREM,
            "method": "Transitive local import closure; exact bytes verified against upstream Git blobs",
            "local_solution_modules": len(local) - 1,
            "challenge_modules": 1,
            "external_import_roots": dict(sorted(Counter(x.split('.')[0] for x in external).items())),
            "external_imports": sorted(external),
            "missing_local_dependencies": [],
        },
        "toolchain": checked_data(lean_root / "lean-toolchain").decode().strip(),
        "mathlib": {"url": "https://github.com/leanprover-community/mathlib4.git", "commit": MATHLIB_COMMIT},
        "dependency_manifest": {
            "method": "Retain mathlib and its eight manifest dependencies from upstream lake-manifest.json, preserving pinned package records",
            "mathlib_manifest_url": f"https://raw.githubusercontent.com/leanprover-community/mathlib4/{MATHLIB_COMMIT}/lake-manifest.json",
            "dependencies": selected_revisions,
            "generated_lake_manifest_sha256": hashlib.sha256(lake_manifest_text.encode()).hexdigest(),
        },
        "comparator_config": config,
        "challenge_placeholder": "The upstream challenge theorem uses sorry intentionally; it is the trusted statement. The solution is in OAI.",
        "files": sorted(records, key=lambda x: x["path"]),
        "generated_lakefile_sha256": hashlib.sha256(package.encode()).hexdigest(),
    }
    (destination / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    for record in records:
        actual = hashlib.sha256((destination / record["path"]).read_bytes()).hexdigest()
        if actual != record["sha256"]:
            raise SystemExit(f"Post-copy hash mismatch: {record['path']}")
    print(json.dumps({
        "copied_lean_files": len(local),
        "solution_closure_files": len(local) - 1,
        "copied_support_files": len(support_files),
        "external_import_roots": manifest["extraction"]["external_import_roots"],
        "all_source_and_destination_hashes_verified": True,
        "destination": str(destination),
    }, indent=2))


if __name__ == "__main__":
    main()
