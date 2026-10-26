#!/usr/bin/env bash
set -euo pipefail

KIND="${1:?Usage: publish-pages.sh provider|geometry|catalog [provider-id]}"
PROVIDER_ID="${2:-}"
ROOT="AreaStatistics"
BASE="${ROOT}/statistics"
GIT_NAME="Kartensammlung Builds"
GIT_EMAIL="actions@users.noreply.github.com"

publish_once() {
	local attempt="$1"
	local worktree
	worktree="$(mktemp -d)"
	rmdir "$worktree"
	if git ls-remote --exit-code --heads origin gh-pages >/dev/null 2>&1; then
		git fetch --no-tags origin gh-pages
		git worktree add --detach "$worktree" FETCH_HEAD
		(
			cd "$worktree"
			git checkout -B gh-pages
		)
	else
		git worktree add --detach "$worktree" HEAD
		(
			cd "$worktree"
			git checkout --orphan gh-pages
			git rm -r -f --ignore-unmatch . >/dev/null
			find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
		)
	fi

	touch "$worktree/.nojekyll"
	mkdir -p "$worktree/$BASE"

	case "$KIND" in
		provider)
			: "${PROVIDER_ID:?provider-id required}"
			test -s "dist/statistics/$PROVIDER_ID/index.json"
			test -s "dist/statistics/index.json"
			mkdir -p "$worktree/$BASE/$PROVIDER_ID"
			rsync -a --delete "dist/statistics/$PROVIDER_ID/" "$worktree/$BASE/$PROVIDER_ID/"
			cp "dist/statistics/index.json" "$worktree/$BASE/index.json"
			;;
		geometry)
			for file in world-admin.pmtiles area-registry-countries.json build-metadata.json; do
				test -s "dist/$file"
				mkdir -p "$worktree/$ROOT"
				cp "dist/$file" "$worktree/$ROOT/$file"
			done
			;;
		catalog)
			test -s "dist/statistics/index.json"
			cp "dist/statistics/index.json" "$worktree/$BASE/index.json"
			;;
		*)
			echo "Unknown publication type: $KIND" >&2
			exit 1
			;;
	esac

	(
		cd "$worktree"
		git config user.name "$GIT_NAME"
		git config user.email "$GIT_EMAIL"
		git add -A
		if ! git diff --cached --quiet; then
			git commit -m "Publish $KIND ${PROVIDER_ID:-} (${GITHUB_RUN_ID:-manual})"
			git push origin HEAD:gh-pages
		fi
	)
	local status=$?
	git worktree remove --force "$worktree" || true
	return "$status"
}

for attempt in 1 2 3 4 5; do
	if publish_once "$attempt"; then
		if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
			: "${GH_TOKEN:?GH_TOKEN required for Pages deployment dispatch}"
			gh workflow run publish-site.yml --ref main
		fi
		exit 0
	fi
	echo "Concurrent publishing update; retry $attempt" >&2
	sleep "$((attempt * 3))"
done
echo "GitHub Pages publication failed after retries." >&2
exit 1
