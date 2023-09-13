- name: gcr.io/kaniko-project/executor:latest
  args: [ "--dockerfile=dockerfiles/generated/base/${path}/Dockerfile",
          "--destination=${region}-docker.pkg.dev/cykubed/public/${destpath}:${tag}",
          "--cache=true"]
