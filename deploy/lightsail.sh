#!/usr/bin/env bash
set -euo pipefail

commit=${1:-}
[[ "$commit" =~ ^[a-f0-9]{40}$ ]] || exit 1
cd /opt/auction-lab

exec 9>.git/auction-lab-deploy.lock
flock 9

[[ $(git branch --show-current) == main ]] || { echo 'Expected a main checkout.' >&2; exit 1; }
[[ -f .env && -z $(git status --porcelain --untracked-files=no) ]] || {
  echo 'The checkout must be clean and have a server .env file.' >&2
  exit 1
}

git fetch origin refs/heads/main
[[ $(git rev-parse FETCH_HEAD) == "$commit" ]] || { echo 'A newer main commit exists.' >&2; exit 1; }
[[ -z $(git ls-tree "$commit" -- .env) ]] || { echo 'The release tracks .env.' >&2; exit 1; }
git merge --ff-only "$commit"
[[ $(git rev-parse HEAD) == "$commit" ]] || { echo 'The checkout does not match the verified commit.' >&2; exit 1; }

docker compose build web
docker compose up -d --wait db
docker compose run --rm --no-deps web python manage.py migrate --noinput
docker compose up -d --no-deps --wait web
