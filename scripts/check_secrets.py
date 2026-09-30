"""Scan Git's index, never print matched secrets. Run before every public commit."""
import re
import subprocess
import sys
from pathlib import PurePosixPath

names = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
failed = []
for name in filter(None, names):
    base = PurePosixPath(name).name
    if (base.startswith(".env") and base != ".env.example") or base.endswith((".pem", ".key", ".dump")):
        failed.append(name)
        continue
    content = subprocess.check_output(["git", "show", f":{name}"])
    if re.search(rb"sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY", content):
        failed.append(name)
if failed:
    print("Secret check failed in: " + ", ".join(failed))
    sys.exit(1)
print("Secret check passed: no environment files or recognized credentials in Git's index.")
