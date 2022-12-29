import logging
import subprocess
import time

from kubernetes import client

from build import clone_repos, create_node_environment, get_specs
from common.exceptions import BuildFailedException
from common.k8common import get_job_env, get_batch_api, NAMESPACE
from common.schemas import NewTestRun
from settings import settings
from utils import get_async_client, runcmd, upload_to_cache

running = False


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
        command=['run', str(testrun.id)],
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


async def clone_and_build(testrun_id: int):
    """
    Clone and build
    """
    async with get_async_client() as httpclient:

        async def post_status(status: str):
            resp = await httpclient.put(f'{settings.MAIN_API_URL}/testrun/{testrun_id}/status',
                                        json=dict(status=status))
            if resp.status_code != 200:
                raise BuildFailedException(f"Failed to update status for run {testrun_id}: bailing out")

        r = await httpclient.get(f'{settings.MAIN_API_URL}/testrun/{testrun_id}')
        if r.status_code != 200:
            raise BuildFailedException(f"Failed to fetch testrun {testrun_id}")

        testrun = NewTestRun.parse_obj(r.json())
        t = time.time()

        try:
            # clone
            wdir = clone_repos(testrun.project.url, testrun.branch)
            if not testrun.sha:
                testrun.sha = subprocess.check_output(['git', 'rev-parse', testrun.branch], cwd=wdir,
                                                      text=True).strip('\n')

            # install node packages first (or fetch from cache)
            await create_node_environment(testrun, wdir, httpclient)

            # now we can determine the specs
            specs = get_specs(wdir)

            # tell cykube
            r = await httpclient.put(f'{settings.MAIN_API_URL}/agent/testrun/{testrun.id}/specs',
                                     json={'specs': specs, 'sha': testrun.sha})
            if r.status_code != 200:
                raise BuildFailedException("Failed to update cykube with list of specs - bailing out")

            if not specs:
                logging.info("No specs - nothing to test")
                await post_status('passed')
                return

            # start the runner jobs - that way the cluster has a head start on spinning
            # up new nodes
            logging.info(f"Starting {testrun.project.parallelism} Jobs")
            create_runner_jobs(testrun)

            # build the app
            await post_status('building')
            logging.info(f"Found {len(specs)} spec files")
            logging.info(f"Building app")
            runcmd(f'{testrun.project.build_cmd}', cwd=wdir)

            # tar it up
            logging.info("Create distribution and cleanup")
            filename = f'/tmp/{testrun.sha}.tar.lz4'
            # tarball everything
            runcmd(f'tar cf {filename} . -I lz4', cwd=wdir)
            # upload to cache
            await upload_to_cache(httpclient, filename)
            # now we can run
            await post_status('running')
            t = time.time() - t
            logging.info(f"Distribution created in {t:.1f}s")

        except Exception as ex:
            logging.exception("Failed to create build")
