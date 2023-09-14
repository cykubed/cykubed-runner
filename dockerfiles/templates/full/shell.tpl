#!/bin/bash
set -e
$steps

http POST ${cykubed_api_url}/admin/runner/image -A bearer -a $$CYKUBED_API_TOKEN  < dockerfiles/generated/full/cykubed-payload.json
http POST $$SLACK_HOOK_URL < dockerfiles/generated/full/slack-payload.json
