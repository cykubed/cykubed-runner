timeout: 3600s
availableSecrets:
  secretManager:
  - versionName: projects/cykubed/secrets/SLACK_HOOK_URL/versions/1
    env: 'SLACK_HOOK_URL'
  - versionName: projects/cykubed/secrets/cykubed-api-token/versions/1
    env: 'CYKUBED_API_TOKEN'
steps:

- name: 'gcr.io/cloud-builders/git'
  script: |
    git config -f .gitmodules submodule.src/cykubedrunner/common.url https://source.developers.google.com/p/cykubed/r/github_cykubed_cykubed-common
    git submodule init
    git submodule update

$steps

- name: alpine/httpie
  id: Update Cykubed app with latest runner images and notify Slack
  secretEnv: ['SLACK_HOOK_URL', 'CYKUBED_API_TOKEN']
  script: |
    http POST https://api.cykubed.com/admin/docker/image -A bearer -a $$CYKUBED_API_TOKEN  < dockerfiles/generated/full/cykubed-payload.json
    http POST $$SLACK_HOOK_URL < dockerfiles/generated/full/slack-payload.json
