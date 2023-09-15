import json
import os.path
import shutil
import click

from dockerfiles.common import NODE_MAJOR_VERSIONS, BROWSERS, GENERATION_DIR, BASE_DOCKERFILE, render


@click.command()
@click.option('--region', default='us', help='GCP region')
@click.option('-t', '--tag', required=True, help='Build tag')
@click.option('-ff', '--firefoxvs', default='117.0', help='Firefox version')
def generate(region: str, tag: str, firefoxvs: str):
    """
    Generate the base Dockerfiles for various combinations of browser and node.
    Note that these are only intended to be base images i.e. they have not installed cykubedrunner,
    as the bases images rarely change.

    Defaults to generating Dockerfiles for all 3 browsers seperately, then all together,
    for each major version of Node.

    The script also generates a cloudbuild.yaml file for use in Google Cloud Build to actually
    generate the images (using Kaniko)
    """
    shutil.rmtree(GENERATION_DIR + '/base', ignore_errors=True)

    all_base_paths = []

    os.makedirs(GENERATION_DIR + '/base/base', exist_ok=True)
    shutil.copy(BASE_DOCKERFILE, GENERATION_DIR + '/base/base')
    base_context = dict(firefox_version=firefoxvs, region=region, tag=tag)
    context = dict(path='base', destpath='base', **base_context)
    cloudbuild_steps = [render('base/cloudbuild-step', context)]
    shell_steps = [render('base/shell-step', context)]

    for node_major in NODE_MAJOR_VERSIONS:
        node_base = f'node-{node_major}'
        context = dict(node_major=node_major, **base_context)
        render('base/node', context, f'base/{node_base}')

        all_base_paths.append({'image': f'base-{node_base}', 'tag': tag, 'node_major': node_major, 'browsers': []})

        context = dict(path=node_base, destpath=f'base-{node_base}', node_major=node_major, **base_context)
        cloudbuild_steps.append(render('base/cloudbuild-step', context))
        shell_steps.append(render('base/shell-step', context))

        all_browsers = []
        for browser in BROWSERS:
            browser_snippet = render(f'base/{browser}', base_context)
            all_browsers.append(browser_snippet)
            path = f'{node_base}-{browser}'
            render('base/base-browser', dict(browsers=browser_snippet, node_major=node_major,
                                             **base_context),
                   f'base/{path}')

            all_base_paths.append({'image': f'base-{path}', 'tag': tag, 'node_major': node_major,
                                   'browsers': [browser]})

            context = dict(path=path, destpath=f'base-{path}', **base_context)

            cloudbuild_steps.append(render('base/cloudbuild-step', context))
            shell_steps.append(render('base/shell-step', context))

        # all browsers
        if len(all_browsers) > 1:
            path = f'{node_base}-chrome-edge-firefox'
            context = dict(node_major=node_major, destpath=f'base-{path}',
                           browsers="\n".join(all_browsers), **base_context)
            render('base/base-browser', context, f'base/{path}')

            all_base_paths.append({'image': f'base-{path}', 'tag': tag, 'node_major': node_major,
                                   'browsers': BROWSERS})

            context['path'] = path
            cloudbuild_steps.append(render('base/cloudbuild-step', context))
            shell_steps.append(render('base/shell-step', context))

    # generate cloudbuild.yaml for the base image build
    render('base/cloudbuild', dict(steps="\n".join(cloudbuild_steps),
                                   **base_context), output_file='base/cloudbuild.yaml')

    # and a bash script
    render('base/shell',
           dict(slack_hook_url=os.environ.get('SLACK_HOOK_URL'),
                steps="\n".join(shell_steps),
                **base_context), output_file='base/build.sh')

    with open(os.path.join(GENERATION_DIR, 'base', 'all-base-images.json'), 'w') as f:
        f.write(json.dumps(all_base_paths, indent=4))



if __name__ == '__main__':
    generate()
