- name: gcr.io/kaniko-project/executor:latest
  args: [ "--dockerfile=dockerfiles/generated/${path}/Dockerfile",
          "--destination=${region}-docker.pkg.dev/cykubed/public/${path}:${tag}",
          "--cache=true"]
