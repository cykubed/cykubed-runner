timeout: 900s
availableSecrets:
  secretManager:
  - versionName: projects/cykubed/secrets/SLACK_HOOK_URL/versions/1
    env: 'SLACK_HOOK_URL'
steps:

$steps

- name: gcr.io/cloud-builders/curl
  id: Notify Slack
  secretEnv: ['SLACK_HOOK_URL']
  script: |
    echo "{\"text\":\"Cykubed runner images created with tag ${tag}\"}" > payload.json
    /usr/bin/curl -X POST -H 'Content-type: application/json' --data "@payload.json" $$SLACK_HOOK_URL
