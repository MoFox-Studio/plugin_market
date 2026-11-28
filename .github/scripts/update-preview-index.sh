#!/usr/bin/env bash
#
# 把 gh-pages 上现有的 PR 预览目录整理成根目录的 previews.json，
# 供预览站首页直接读取，避免匿名调用 GitHub API 触发限流。
#
# 需要环境变量：
#   GH_TOKEN             具有 contents: write 权限的 token
#   GITHUB_REPOSITORY    owner/repo
#   PREVIEW_BRANCH       默认 gh-pages
#   UMBRELLA_DIR         默认 pr-preview

set -euo pipefail

: "${GH_TOKEN:?缺少 GH_TOKEN}"
: "${GITHUB_REPOSITORY:?缺少 GITHUB_REPOSITORY}"

repo="${GITHUB_REPOSITORY}"
branch="${PREVIEW_BRANCH:-gh-pages}"
umbrella="${UMBRELLA_DIR:-pr-preview}"
api="repos/${repo}"

previews="[]"
if raw=$(gh api "${api}/contents/${umbrella}?ref=${branch}" 2>/dev/null); then
  previews=$(jq -c '
    [ .[]
      | select(.type == "dir")
      | .name
      | select(test("^pr-[0-9]+$"))
      | ltrimstr("pr-")
      | tonumber
    ] | sort | reverse
  ' <<<"$raw")
fi

payload=$(jq -c -n \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --argjson previews "$previews" \
  '{ generatedAt: $generated_at, previews: $previews }')

head_sha=$(gh api "${api}/git/ref/heads/${branch}" --jq '.object.sha')
base_tree=$(gh api "${api}/git/commits/${head_sha}" --jq '.tree.sha')

blob_sha=$(jq -c -n --arg content "$payload" '{ content: $content, encoding: "utf-8" }' \
  | gh api "${api}/git/blobs" -X POST --input - --jq '.sha')

tree_sha=$(jq -c -n --arg base "$base_tree" --arg blob "$blob_sha" \
  '{ base_tree: $base, tree: [{ path: "previews.json", mode: "100644", type: "blob", sha: $blob }] }' \
  | gh api "${api}/git/trees" -X POST --input - --jq '.sha')

commit_sha=$(jq -c -n --arg tree "$tree_sha" --arg parent "$head_sha" \
  '{ message: "chore: 更新预览索引", tree: $tree, parents: [ $parent ] }' \
  | gh api "${api}/git/commits" -X POST --input - --jq '.sha')

gh api "${api}/git/refs/heads/${branch}" -X PATCH -f sha="$commit_sha" --jq '.object.sha' >/dev/null

echo "已更新 ${branch}/previews.json：${previews}"