#!/bin/bash
set -e
BUMP="${1:-minor}"
NOTES="${2:-Updated}"

VERSION=$(poetry version $BUMP -s)

git add pyproject.toml
git commit -m "${NOTES}"
git tag $VERSION
git push origin tag $VERSION
