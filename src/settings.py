import os

from pydantic import BaseSettings


class RunnerSettings(BaseSettings):
    API_TOKEN: str = 'cykubeauth'

    K8: bool = True

    NAMESPACE = 'cykube'

    SERVER_START_TIMEOUT: int = 60
    CYPRESS_RUN_TIMEOUT: int = 10*60

    KEEPALIVE_ON_FAILURE = False

    ENCODING = 'utf8'

    TEST = False

    MAX_HTTP_RETRIES = 10
    MAX_HTTP_BACKOFF = 60

    MAIN_API_URL: str = 'https://api.cykubed.com'

    SENTRY_DSN: str = None

    HOSTNAME: str = None  # for testing

    SCRATCH_DIR = '/tmp/cykubed/scratch'
    BUILD_DIR = '/tmp/cykubed/build'

    RW_BUILD_DIR = '/tmp/cykubed/build'

    SERVER_PORT = 9000

    @property
    def src_dir(self):
        return os.path.join(self.BUILD_DIR, 'build')

    @property
    def dist_dir(self):
        return os.path.join(self.SCRATCH_DIR, 'build')

    def get_results_dir(self):
        return os.path.join(self.SCRATCH_DIR, 'results')

    def get_temp_dir(self):
        return os.path.join(self.SCRATCH_DIR, 'tmp')

    def get_screenshots_folder(self):
        return os.path.join(self.get_results_dir(), 'screenshots')

    def get_videos_folder(self):
        return os.path.join(self.get_results_dir(), 'videos')

    def init_build_dirs(self):
        os.makedirs(self.dist_dir, exist_ok=True)
        os.makedirs(self.BUILD_DIR, exist_ok=True)
        os.makedirs(self.get_temp_dir(), exist_ok=True)
        os.makedirs(self.get_videos_folder(), exist_ok=True)
        os.makedirs(self.get_screenshots_folder(), exist_ok=True)


settings = RunnerSettings()
