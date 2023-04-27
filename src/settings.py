import os
import shutil

from pydantic import BaseSettings


class RunnerSettings(BaseSettings):
    API_TOKEN: str = 'cykubeauth'

    K8: bool = True

    NAMESPACE = 'cykube'

    SERVER_START_TIMEOUT: int = 60
    CYPRESS_RUN_TIMEOUT: int = 10*60

    ENCODING = 'utf8'

    TEST = False

    MAX_HTTP_RETRIES = 10
    MAX_HTTP_BACKOFF = 60

    AGENT_URL: str = 'http://127.0.0.1:5000'
    MAIN_API_URL: str = 'https://app.cykube.net/api'

    SENTRY_DSN: str = None

    HOSTNAME: str = None  # for testing

    SCRATCH_DIR = '/tmp/cykubed/scratch'
    BUILD_DIR = '/tmp/cykubed/build'
    NODE_CACHE_DIR = '/tmp/cykubed/nodecache'

    def get_yarn_cache_dir(self):
        return os.path.join(self.NODE_CACHE_DIR, '.yarn_cache')

    def get_results_dir(self):
        return os.path.join(self.SCRATCH_DIR, 'results')

    def get_temp_dir(self):
        return os.path.join(self.SCRATCH_DIR, 'tmp')

    def get_screenshots_folder(self):
        return os.path.join(self.get_results_dir(), 'screenshots')

    def get_videos_folder(self):
        return os.path.join(self.get_results_dir(), 'videos')

    def init_build_dirs(self):

        if os.path.exists(self.BUILD_DIR):
            # probably running as developer
            shutil.rmtree(self.BUILD_DIR, ignore_errors=True)

        os.makedirs(self.BUILD_DIR, exist_ok=True)
        os.makedirs(self.get_temp_dir(), exist_ok=True)
        os.makedirs(self.get_videos_folder(), exist_ok=True)
        os.makedirs(self.get_screenshots_folder(), exist_ok=True)


settings = RunnerSettings()
