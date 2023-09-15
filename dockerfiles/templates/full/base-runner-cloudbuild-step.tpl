- name: 'gcr.io/cloud-builders/git'
  script: |
    git config -f .gitmodules submodule.src/lib/common.url https://source.developers.google.com/p/cykubed/r/github_cykubed_cykubed-common
    git submodule init
    git submodule update
- name: gcr.io/kaniko-project/executor:latest
  args: [ "--dockerfile=dockerfiles/base/runner/Dockerfile",
          "--destination=${region}-docker.pkg.dev/cykubed/public/base-runner:${tag}",
          "--cache=true"]
