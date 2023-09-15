- name: gcr.io/kaniko-project/executor:latest
  args: [ "--dockerfile=dockerfiles/base/runner/Dockerfile",
          "--destination=${region}-docker.pkg.dev/cykubed/public/base-runner:${tag}",
          "--cache=true"]
