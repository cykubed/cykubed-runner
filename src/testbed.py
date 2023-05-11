import os
import subprocess

from common.redisutils import sync_redis
from common.utils import utcnow
from cypress import RedisLogPipe
from settings import settings


def runspec():
    json_reporter = '/usr/app/json-reporter.js'

    env = os.environ.copy()
    env['CYPRESS_CACHE_FOLDER'] = f'{settings.RW_BUILD_DIR}/cypress_cache'
    env['PATH'] = f'node_modules/.bin:{env["PATH"]}'

    dist_dir = os.path.join(settings.RW_BUILD_DIR, 'dist')
    results_dir = settings.get_results_dir()
    results_file = f'{results_dir}/out.json'
    base_url = f'http://localhost:9000'

    args = ['cypress', 'run',
            '-q',
            '--browser', 'chrome',
            '-s', 'cypress/e2e/stuff/test2.spec.ts',
            '--reporter', json_reporter,
            '-o', f'output={results_file}',
            '-c', f'screenshotsFolder={settings.get_screenshots_folder()},screenshotOnRunFailure=true,'
                  f'baseUrl={base_url},video=false,videosFolder={settings.get_videos_folder()}']

    return subprocess.run(args,
                          timeout=settings.CYPRESS_RUN_TIMEOUT, capture_output=True,
                          env=env, cwd=dist_dir)



def run():
    started = utcnow()
    spec_deadline = 60
    hang_timeout = 3

    logpipe = RedisLogPipe(30, 'cypress/e2e/test/fish.ts')
    with subprocess.Popen(['/home/nick/.cache/pypoetry/virtualenvs/cykube-runner-xzjAvd4V-py3.10/bin/python',
                           'printtest.py'], encoding=settings.ENCODING,
                          text=True,
                          stdout=logpipe, stderr=logpipe) as proc:
        while (utcnow() - started).seconds < spec_deadline and proc.returncode is None:
            initial_lines = logpipe.lines
            try:
                retcode = proc.wait(hang_timeout)
                print(f'Finished with code {retcode}')
                break
            except KeyboardInterrupt:
                proc.kill()
                break
            except subprocess.TimeoutExpired:
                if logpipe.lines == initial_lines:
                    print(f'Assumed hanging - quit')
                    proc.kill()
                    break

    print("finished!")
    msgs = sync_redis().lrange(logpipe.key, 0, -1)
    print(msgs)


run()
