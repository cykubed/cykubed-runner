import json
import os
import subprocess

import click

from cykubedrunner.common import schemas
from dockerfiles.common import GENERATION_DIR, render, read_base_image_details

BRANCH = "master"


def cmd(args: str, silent=False) -> str:
    p = subprocess.run(args, capture_output=True, text=True, shell=True)
    if p.returncode != 0:
        raise click.ClickException(f'{args} failed with return code {p.returncode} and output {p.stdout} (error={p.stderr})')
    if not silent:
        print(p.stdout)
    return p.stdout.strip()


@click.command(help='Generate a new release of the runner')
@click.option('--region', default='us', help='GCP region')
@click.option('-b', '--bump', type=click.Choice(['major', 'minor', 'patch']),
              default='patch',
              help='Type of version bump')
@click.option('-g', '--generate_only', is_flag=True, help='Generate only')
@click.option('-n', '--notes', type=str, required=True, help='Release notes')
def generate(region: str, bump: str, notes: str, generate_only: bool):

    if not generate_only and cmd('git branch --show-current') != 'master':
        raise click.BadParameter('Not on master branch')

    # run the tests first as a sanity check
    if not generate_only:
        cmd('py.test', True)

    # bump and get the tag
    tag = cmd(f"poetry version {bump} -s")

    base_image_details = read_base_image_details()
    base_tag = base_image_details['tag']

    steps = [render('full/base-runner-cloudbuild-step', dict(tag=tag, region=region))]
    bash_steps = [render('full/base-runner-shell-step', dict(tag=tag, region=region))]

    new_runner_images = []
    base_context = dict(base_tag=base_tag, region=region, tag=tag)
    # now generate full images for all variants
    for details in base_image_details['bases']:
        base_image = details['image']
        path = base_image[5:]
        render('full/dockerfile',
               dict(base_image=f'{base_image}:{base_tag}', **base_context),
               f'full/{path}')
        context = dict(path=path, **base_context)
        steps.append(render('full/cloudbuild-step', context))
        bash_steps.append(render('full/shell-step', context))

        browsers = details['browsers']
        new_runner_images.append(
            schemas.NewRunnerImage(tag=tag,
                                   image=f'{region}-docker.pkg.dev/cykubed/public/{path}',
                                   description=notes,
                                   node_version=details['node_major'],
                                   chrome='chrome' in browsers,
                                   firefox='firefox' in browsers,
                                   edge='edge' in browsers))

    payload_obj = [i.dict() for i in new_runner_images]
    with open(os.path.join(GENERATION_DIR, 'full/cykubed-payload.json'), 'w') as f:
        f.write(json.dumps(payload_obj, indent=4))

    # generate cloudbuild.yaml for the base image build
    render('full/cloudbuild', dict(steps="\n".join(steps), tag=tag, region=region),
           output_file='full/cloudbuild.yaml')

    # generate build.sh for the base image build
    render('full/shell', dict(steps="\n".join(bash_steps), tag=tag, region=region,
                              cykubed_api_url=os.environ.get('MAIN_API_URL', 'https://api.cykubed.com')),
           output_file='full/build.sh')

    # slack payload
    render('full/slack', dict(tag=tag), output_file='full/slack-payload.json')

    if not generate_only:
        # all done: commit and tag
        cmd(f'git add dockerfiles/generated')
        cmd(f'git add pyproject.toml')
        cmd(f'git commit -m "{notes}"')
        cmd(f'git tag -a {tag} -m "New release:\n{notes}"')
        cmd(f'git push origin {tag}')


if __name__ == '__main__':
    generate()
