import os.path
import shutil
from string import Template
import click

NODE_MAJOR_VERSIONS = ['14'] #, '16', '18', '20']
BROWSERS = ['chrome-current'] #, 'edge', 'firefox']
BASE_URL = 'us-east1-docker.pkg.dev/cykubed/public'
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
DOCKERFILE_DIR = os.path.join(os.path.dirname(__file__), 'generated')


def render(template_name, context, outputdir=None) -> str:
    template_file = os.path.join(TEMPLATE_DIR, template_name+'.tpl')
    with open(template_file, 'r') as f:
        s = Template(f.read()).substitute(context)

    if outputdir:
        ddir = os.path.join(DOCKERFILE_DIR, outputdir)
        os.makedirs(ddir, exist_ok=True)
        with open(os.path.join(ddir, 'Dockerfile'), 'w') as f:
            f.write(s)
    return s.strip()


@click.command()
@click.option('--region', default='us', help='GCP region')
@click.option('-c', '--clear', type=bool, default=False, help='Clear any existing generated files')
@click.option('-t', '--tag', required=True, help='Build tag')
@click.option('-ff', '--firefoxvs', default='117.0', help='Firefox version')
def generate(region: str, tag: str, clear: bool, firefoxvs: str):
    """
    Generate the base Dockerfiles for various combinations of browser and node.
    Note that these are only intended to be base images i.e. they have not installed cykubedrunner,
    as the bases images rarely change.

    Defaults to generating Dockerfiles for all 3 browsers seperately, then all together,
    for each major version of Node.

    The script also generates a cloudbuild.yaml file for use in Google Cloud Build to actually
    generate the images (using Kaniko)
    """
    if clear:
        shutil.rmtree(DOCKERFILE_DIR)

    base_context = dict(firefox_version=firefoxvs, region=region, tag=tag)
    steps = [render('cloudbuild-step', dict(path='base', **base_context))]

    for node_major in NODE_MAJOR_VERSIONS:
        node_base = f'node-{node_major}'
        context = dict(node_major=node_major, **base_context)
        render('node', context, node_base)

        steps.append(render('cloudbuild-step',
                            dict(path=node_base, **context)))

        all_browsers = []
        for browser in BROWSERS:
            browser_snippet = render(browser, base_context)
            all_browsers.append(browser_snippet)
            path = f'{node_base}-{browser}'
            render('base-browser', dict(browsers=browser_snippet, **context), path)

            steps.append(render('cloudbuild-step', dict(path=path, **context)))

        # all browsers
        if len(all_browsers) > 1:
            context['browsers'] = "\n".join(all_browsers)
            path=f'{node_base}-chrome-edge-firefox'
            render('base-browser', context, path)
            steps.append(render('cloudbuild-step', dict(path=path, **context)))

    # now generate cloudbuild.yaml
    cb = render('cloudbuild', dict(steps="\n".join(steps),
                                   **base_context))
    with open(os.path.join(DOCKERFILE_DIR, 'cloudbuild.yaml'), 'w') as f:
        f.write(cb)


if __name__ == '__main__':
    generate()
