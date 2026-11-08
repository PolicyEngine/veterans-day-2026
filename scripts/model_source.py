"""Record which policyengine-us build produced an output.

A run may use the pinned release from requirements.txt or, with PYTHONPATH,
a policyengine-us checkout carrying unreleased fixes. Outputs record which.
"""

import importlib.metadata
import pathlib
import subprocess

import policyengine_us


def model_source() -> dict:
    package = pathlib.Path(policyengine_us.__file__).resolve().parent
    source = {
        "policyengine_us_installed": importlib.metadata.version("policyengine-us"),
        "policyengine_core": importlib.metadata.version("policyengine-core"),
    }
    if "site-packages" in package.parts:
        source["policyengine_us"] = source["policyengine_us_installed"]
        source["policyengine_us_from"] = "release"
        return source

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(package.parent), *args],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    source["policyengine_us"] = f"checkout {git('rev-parse', 'HEAD')[:10]}"
    source["policyengine_us_from"] = "checkout"
    source["policyengine_us_branch"] = git("rev-parse", "--abbrev-ref", "HEAD")
    source["policyengine_us_dirty"] = bool(git("status", "--porcelain"))
    return source
