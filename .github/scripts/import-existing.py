#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
from pathlib import Path

SOURCE = Path("/tmp/ks-area-statistics-source")
DEST = Path.cwd()
PUBLIC_BASE = "https://peter-alexander.github.io/ks-AreaStatistics/AreaStatistics"

for directory in ("config", "docs", "scripts"):
	shutil.copytree(SOURCE / directory, DEST / directory, dirs_exist_ok=True)

for filename in (".gitignore", "requirements.txt"):
	shutil.copy2(SOURCE / filename, DEST / filename)

shutil.copy2(
	SOURCE / ".github/scripts/tippecanoe-country-geometry.sh",
	DEST / ".github/scripts/tippecanoe-country-geometry.sh",
)

workflow_dir = DEST / ".github/workflows"
workflow_dir.mkdir(parents=True, exist_ok=True)
for source in sorted((SOURCE / ".github/workflows").glob("*.yml")):
	content = source.read_text(encoding="utf-8")
	provider_match = re.search(r"(?m)^\s+PROVIDER_ID:\s*([a-z0-9-]+)\s*$", content)
	provider = provider_match.group(1) if provider_match else "world-bank"
	if source.name == "build-country-geometry.yml":
		kind = "geometry"
	elif source.name == "publish-statistics-catalog.yml":
		kind = "catalog"
	else:
		kind = "provider"

	content = content.replace("https://tiles.radlobby.at/AreaStatistics", PUBLIC_BASE)
	content = content.replace("permissions:\n  contents: read", "permissions:\n  contents: write")

	lines = content.splitlines(keepends=True)
	result = []
	skip = False
	for line in lines:
		if line.startswith("      - name: "):
			title = line.strip().removeprefix("- name: ")
			skip = (
				title.startswith("Install deployment tools")
				or title.startswith("Install deploy dependency")
				or title.startswith("Deploy")
				or title.startswith("Verify public")
				or title.startswith("Verify browser access")
			)
		if skip:
			continue
		if any(old in line for old in (
			"bash -n .github/scripts/deploy-area-statistics.sh",
			"bash -n .github/scripts/deploy-world-bank-statistics.sh",
			"bash -n .github/scripts/lftp-upload.sh",
		)):
			continue
		result.append(line)
	content = "".join(result).rstrip() + "\n"

	deploy = (
		"      - name: Publish GitHub Pages files\n"
		"        if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'\n"
		"        shell: bash\n"
		"        run: |\n"
		"          set -euo pipefail\n"
		f"          bash .github/scripts/publish-pages.sh {kind} {provider if kind == 'provider' else ''}\n"
	)
	diagnostic = "      - name: Upload diagnostics on failure"
	if diagnostic in content:
		content = content.replace(diagnostic, deploy + "\n" + diagnostic, 1)
	else:
		content += "\n" + deploy

	# Do not rebuild every provider just because the entire build suite migrated.
	content = content.replace(
		"      - \".github/workflows/" + source.name + "\"",
		"      - \".github/workflows/" + source.name + "\"",
	)
	(workflow_dir / source.name).write_text(content, encoding="utf-8")

for path in [*list((DEST / "scripts").glob("*")), *list((DEST / "docs").glob("*"))]:
	if not path.is_file() or path.suffix not in {".py", ".md", ".R", ".json"}:
		continue
	try:
		content = path.read_text(encoding="utf-8")
	except UnicodeDecodeError:
		continue
	updated = content.replace("https://tiles.radlobby.at/AreaStatistics", PUBLIC_BASE)
	if content != updated:
		path.write_text(updated, encoding="utf-8")

(DEST / "README.md").write_text(
	"# ks-AreaStatistics\n\nBuilds und GitHub-Pages-Veröffentlichung der Gebietsstatistiken für die Kartensammlung.\n",
	encoding="utf-8",
)

# Prevent the one-off migration workflow from remaining in the published source tree.
(DEST / ".github/workflows/import-existing.yml").unlink(missing_ok=True)
(DEST / ".github/scripts/import-existing.py").unlink(missing_ok=True)
print(f"Migrated {len(list(workflow_dir.glob('*.yml')))} workflows.")
