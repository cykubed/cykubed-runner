#!/bin/bash
set -e
NOTES="${1:-Updated dependencies}"
BUMP="${2:-minor}"

VERSION=$(poetry version $BUMP -s)

git add pyproject.toml
git commit -m "${NOTES}"
git tag $VERSION
git push origin tag $VERSION
