timeout: 3600s
availableSecrets:
  secretManager:
  - versionName: projects/cykubed/secrets/SLACK_HOOK_URL/versions/1
    env: 'SLACK_HOOK_URL'
steps:
- name: gcr.io/kaniko-project/executor:latest
  args: [ "--dockerfile=dockerfiles/generated/base/cypress/Dockerfile",
          "--destination=${region}-docker.pkg.dev/cykubed/public/cypress-base:${tag}",
          "--cache=true"]

$steps

- name: gcr.io/cloud-builders/curl
  id: Notify Slack
  secretEnv: ['SLACK_HOOK_URL']
  script: |
    echo "{\"text\":\"Cykubed runner *base* images created with tag ${tag}\"}" > payload.json
    /usr/bin/curl -X POST -H 'Content-type: application/json' --data "@payload.json" $$SLACK_HOOK_URL
