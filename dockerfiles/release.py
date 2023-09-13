import json
import os
import subprocess

import click

from dockerfiles.genbase import GENERATION_DIR, render


@click.command(help='Generate a new release of the runner')
@click.option('--region', default='us', help='GCP region')
def generate(region: str):
    # get the tag
    p = subprocess.run("git describe --tags --abbrev=0", capture_output=True, text=True, shell=True)
    tag = p.stdout.strip()

    with open(os.path.join(GENERATION_DIR, 'base', 'all-base-images.json'), 'r') as f:
        all_base_images = json.loads(f.read())

    steps = []
    base_context=dict(region=region)
    # now generate full images for all variants
    for img in all_base_images:
        prefix = img.split(':')[0][5:]
        render('full/dockerfile',
               dict(base_image=img, **base_context), f'full/{prefix}')
        steps.append(render('full/cloudbuild-step', dict(path=prefix, destpath=prefix, tag=tag,
                                                         **base_context)))

    # generate cloudbuild.yaml for the base image build
    cb = render('full/cloudbuild', dict(steps="\n".join(steps), tag=tag, **base_context))
    with open(os.path.join(GENERATION_DIR, 'full', 'cloudbuild.yaml'), 'w') as f:
        f.write(cb)


if __name__ == '__main__':
    generate()
