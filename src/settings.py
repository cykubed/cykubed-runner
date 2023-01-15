import enum

from pydantic import BaseSettings


class JobMode(str, enum.Enum):
    K8 = 'k8'
    inline = 'inline'
    thread = 'thread'


class AppSettings(BaseSettings):
    API_TOKEN: str = 'cykubeauth'

    TEST_RUN_TIMEOUT: int = 30 * 60
    SPEC_FILE_TIMEOUT: int = 5 * 60
    DIST_BUILD_TIMEOUT: int = 10 * 60
    SERVER_START_TIMEOUT: int = 10 * 60
    CYPRESS_RUN_TIMEOUT: int = 10*60

    ENCODING = 'utf8'

    BUILD_TIMEOUT: int = 900

    K8: bool = True

    AGENT_URL: str = 'http://127.0.0.1:5000'
    CACHE_URL: str = 'http://127.0.0.1:5001'
    MAIN_API_URL: str = 'https://app.cykube.net/api'
    BUILD_DIR = '/tmp/cykube/build'
    RESULTS_FOLDER = '/tmp/cykube/results'

    DIST_CACHE_TTL_HOURS: int = 365*24


settings = AppSettings()
