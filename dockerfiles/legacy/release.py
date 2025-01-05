import json
import os
import subprocess

import click
import semver

BRANCH = "master"


def cmd(args: str, silent=False) -> str:
    p = subprocess.run(args, capture_output=True, text=True, shell=True)
    if p.returncode != 0:
        raise click.ClickException(f'{args} failed with return code {p.returncode} and output {p.stdout} (error={p.stderr})')
    if not silent:
        print(p.stdout, p.stderr)
    return p.stdout.strip()


VERSION_FILE = os.path.join(os.path.dirname(__file__), 'versions.json')


@click.command(help='Generate a new release of the runner')
@click.option('-r', '--releasetype', type=click.Choice(['base', 'full']), help='Release type',
              default='full')
@click.option('-b', '--bump', type=click.Choice(['major', 'minor']),
              default='minor',
              help='Type of version bump')
@click.option('-l', '--local', is_flag=True, default=False)
@click.option('-n', '--notes', type=str, required=False, help='Release notes', default='New release')
def generate(bump: str, releasetype: str, notes: str, local: bool):

    branch = cmd('git branch --show-current')
    if branch != 'master':
        raise click.BadParameter('Not on master branch')

    with open(VERSION_FILE) as f:
        versions = json.loads(f.read())

    # bump and get the tag
    oldtag = versions[releasetype]
    ver = semver.Version.parse(oldtag)
    if bump == 'major':
        ver = ver.bump_major()
    else:
        ver = ver.bump_minor()
    newtag = versions[releasetype] = str(ver)

    if releasetype == 'full':
        cmd(f"poetry version {newtag}")

    with open(VERSION_FILE, 'w') as f:
        f.write(json.dumps(versions, indent=4))

    if not local:
        cmd(f'git add dockerfiles/versions.json')
        if releasetype == 'full':
            cmd(f'git add pyproject.toml')
            cmd(f'git tag -a {newtag} -m "New release:\n{notes}"')

        cmd(f'git commit -m "{notes}"')
        cmd(f'git push origin {branch} --tags')

    # now trigger the build
    if releasetype == 'base':
        if local:
            cmd('./scripts/build-base-images.sh')
        else:
            cmd(f'gcloud builds triggers run cykubed-runner-base --substitutions=_BASE_TAG={newtag}'
                f' --branch={branch}')
    else:
        basetag = versions['base']
        if local:
            cmd('./scripts/minikube-build.sh')
        else:
            cmd(f'gcloud builds triggers run cykubed-runners'
                f' --substitutions=_BASE_TAG={basetag},_TAG={newtag} --branch={branch}')


if __name__ == '__main__':
    generate()
