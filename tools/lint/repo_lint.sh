#!/usr/bin/env bash
set -euo pipefail

fail=0
cd "$(git rev-parse --show-toplevel)"

echo "== repo_lint =="

# 1) Secrets reais (tokens/chaves) — ignora docs e .env.example
echo -n "[secrets] "
tmp="$(mktemp)"
git grep -nE '([0-9]{8,10}:[A-Za-z0-9_-]{20,}|gh[pous]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----|BEGIN PRIVATE KEY)' \
  -- . ':!*.md' ':!.env.example' >"$tmp" || true

if [ -s "$tmp" ]; then
  echo "FAIL"
  sed -n '1,120p' "$tmp"
  fail=1
else
  echo "OK"
fi
rm -f "$tmp"

# 2) Arquivos proibidos versionados
echo -n "[forbidden] "
bad="$(git ls-files | egrep -i '(^\.env$|\.db$|\.log$|\.zip$|\.tar(\.gz|\.xz)?$|\.pem$|\.key$|\.pfx$|\.p12$|id_rsa|known_hosts|authorized_keys)' || true)"
if [ -n "$bad" ]; then
  echo "FAIL"
  echo "$bad" | sed -n '1,200p'
  fail=1
else
  echo "OK"
fi

# 3) Python compileall (noc_bot)
if [ -d noc_bot ]; then
  echo -n "[python] "
  python3 -m compileall -q noc_bot && echo "OK" || { echo "FAIL"; fail=1; }
fi

# 4) Top 10 maiores arquivos versionados (informativo)
echo "[largest] top 10 tracked files:"
git ls-files -z | xargs -0 -I{} bash -lc 'printf "%10d  %s\n" "$(wc -c < "{}")" "{}"' | sort -nr | head -n 10

echo "== fim =="
exit "$fail"
