#!/bin/bash
set -e

$steps

echo "{\"text\":\"Cykubed runner *base* images created with tag ${tag}\"}" > slack_payload.json
/usr/bin/curl -X POST -H 'Content-type: application/json' --data "@slack_payload.json" $$SLACK_HOOK_URL
