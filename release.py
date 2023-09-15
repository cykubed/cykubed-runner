import json
import os
import shutil
import subprocess

import click

from cykubedrunner.common import schemas
from dockerfiles.common import GENERATION_DIR, render

BRANCH = "runner-images"


def cmd(args: str) -> str:
    p = subprocess.run(args, capture_output=True, text=True, shell=True)
    if p.returncode != 0:
        raise click.ClickException(f'{args} failed with return code {p.returncode} and output {p.stderr}')
    print(p.stdout)
    return p.stdout.strip()


@click.command(help='Generate a new release of the runner')
@click.option('--region', default='us', help='GCP region')
@click.option('-b', '--bump', type=click.Choice(['major', 'minor', 'patch']),
              default='minor', help='Type of version bump')
@click.option('-n', '--notes', type=str, required=True, help='Release notes')
def generate(region: str, bump: str, notes: str):
    shutil.rmtree(GENERATION_DIR + '/full', ignore_errors=True)

    # bump and get the tag
    tag = cmd(f"poetry version {bump} -s")

    bash_steps = []
    with open(os.path.join(GENERATION_DIR, 'base', 'all-base-images.json'), 'r') as f:
        base_image_details = json.loads(f.read())

    steps = []
    new_runner_images = []
    # now generate full images for all variants
    for details in base_image_details:
        base_image = details['image']
        base_tag = details['tag']
        path = base_image[5:]
        render('full/dockerfile', dict(base_image=f'{base_image}:{base_tag}', region=region),
               f'full/{path}')
        context = dict(path=path, tag=tag, region=region)
        steps.append(render('full/cloudbuild-step', context))
        bash_steps.append(render('full/shell-step', context))

        browsers = details['browsers']
        new_runner_images.append(
            schemas.NewRunnerImage(tag=tag,
                                   image=f'{region}-docker.pkg.dev/cykubed/public/{path}',
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

    # all done: commit and tag
    cmd(f'git add dockerfiles/generated')
    cmd(f'git commit -m "{notes}"')
    cmd(f'git tag -a {tag} -m "New release:\n{notes}"')
    cmd(f'git push --tags origin {BRANCH}')


if __name__ == '__main__':
    generate()
