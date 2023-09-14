timeout: 900s
availableSecrets:
  secretManager:
  - versionName: projects/cykubed/secrets/SLACK_HOOK_URL/versions/1
    env: 'SLACK_HOOK_URL'
  - versionName: projects/cykubed/secrets/cykubed-api-token/versions/1
    env: 'CYKUBED_API_TOKEN'
steps:

$steps

- name: alpine/httpie
  id: Update Cykubed app with latest runner images and notify Slack
  secretEnv: ['SLACK_HOOK_URL', 'CYKUBED_API_TOKEN']
  script: |
    http POST https://api.cykubed.com/admin/runner/image -A bearer -a $$CYKUBED_API_TOKEN  < dockerfiles/generated/full/cykubed-payload.json
    http POST $$SLACK_HOOK_URL < slack-payload.json
