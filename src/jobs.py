from kubernetes import client

from common.k8common import get_job_env, get_batch_api, NAMESPACE
from common.schemas import NewTestRun


def create_runner_jobs(testrun: NewTestRun):
    """
    Create runner jobs
    :param testrun:
    :return:
    """
    job_name = f'cykube-run-{testrun.id}'

    container = client.V1Container(
        image=testrun.project.runner_image,
        name='cykube-runner',
        image_pull_policy='IfNotPresent',
        env=get_job_env(),
        resources=client.V1ResourceRequirements(
            limits={"cpu": testrun.project.runner_cpu,
                    "memory": testrun.project.runner_memory}
        ),
        args=['run', str(testrun.id)],
    )
    pod_template = client.V1PodTemplateSpec(
        spec=client.V1PodSpec(restart_policy="Never",
                              containers=[container]),
        metadata=client.V1ObjectMeta(name='cykube-runner')
    )
    metadata = client.V1ObjectMeta(name=job_name,
                                   labels={"cykube-job": "runner",
                                           "branch": testrun.branch})

    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=metadata,
        spec=client.V1JobSpec(backoff_limit=0, template=pod_template,
                              parallelism=testrun.project.parallelism,
                              ttl_seconds_after_finished=3600),
    )
    get_batch_api().create_namespaced_job(NAMESPACE, job)
