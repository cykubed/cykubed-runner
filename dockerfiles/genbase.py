import json
import os.path
import shutil
from string import Template
import click

NODE_MAJOR_VERSIONS = ['14'] #, '16', '18', '20']
BROWSERS = ['chrome'] #, 'edge', 'firefox']
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
GENERATION_DIR = os.path.join(os.path.dirname(__file__), 'generated')
BASE_DOCKERFILE = os.path.join(os.path.dirname(__file__), 'base/Dockerfile')


def render(template_name, context, outputdir=None) -> str:
    template_file = os.path.join(TEMPLATE_DIR, template_name+'.tpl')
    with open(template_file, 'r') as f:
        s = Template(f.read()).substitute(context)

    if outputdir:
        ddir = os.path.join(GENERATION_DIR, outputdir)
        os.makedirs(ddir, exist_ok=True)
        with open(os.path.join(ddir, 'Dockerfile'), 'w') as f:
            f.write(s)
    return s.strip()


@click.command()
@click.option('--region', default='us', help='GCP region')
@click.option('-c', '--clear', is_flag=True, default=False, help='Clear any existing generated files')
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
        shutil.rmtree(GENERATION_DIR)

    all_base_paths = []

    os.makedirs(GENERATION_DIR + '/base/base', exist_ok=True)
    shutil.copy(BASE_DOCKERFILE, GENERATION_DIR + '/base/base')
    base_context = dict(firefox_version=firefoxvs, region=region, tag=tag)
    steps = [render('base/cloudbuild-step', dict(path='base', destpath='base', **base_context))]

    for node_major in NODE_MAJOR_VERSIONS:
        node_base = f'node-{node_major}'
        context = dict(node_major=node_major, **base_context)
        render('base/node', context, f'base/{node_base}')

        all_base_paths.append(f'base-{node_base}:{tag}')

        steps.append(render('base/cloudbuild-step',
                            dict(path=node_base, destpath=f'base-{node_base}', **context)))

        all_browsers = []
        for browser in BROWSERS:
            browser_snippet = render(f'base/{browser}', base_context)
            all_browsers.append(browser_snippet)
            path = f'{node_base}-{browser}'
            render('base/base-browser', dict(browsers=browser_snippet, **context),
                   f'base/{path}')
            all_base_paths.append(f'base-{path}:{tag}')

            steps.append(render('base/cloudbuild-step',
                                dict(path=path, destpath=f'base-{path}', **context)))

        # all browsers
        if len(all_browsers) > 1:
            context['browsers'] = "\n".join(all_browsers)
            path=f'{node_base}-chrome-edge-firefox'
            render('base/base-browser', context, f'base/{path}')
            all_base_paths.append(f'base-{path}:{tag}')
            steps.append(render('cloudbuild-step', dict(path=path,
                                                        destpath=f'base-{path}', **context)))

    # generate cloudbuild.yaml for the base image build
    cb = render('base/cloudbuild', dict(steps="\n".join(steps),
                                   **base_context))
    with open(os.path.join(GENERATION_DIR, 'base', 'cloudbuild.yaml'), 'w') as f:
        f.write(cb)

    with open(os.path.join(GENERATION_DIR, 'base', 'all-base-images.json'), 'w') as f:
        f.write(json.dumps(all_base_paths, indent=4))



if __name__ == '__main__':
    generate()
