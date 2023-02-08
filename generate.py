import os

base_images = [
    'cypress/browsers:node16.17.0-chrome106',
    'cypress/browsers:node14.7.0-chrome84'
]

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__)))
with open(os.path.join(ROOT, 'templates', 'Dockerfile.tpl'), 'r') as f:
    basetpl = f.read()

for img in base_images:
    tpl = basetpl.format(base=img)
    tdir = os.path.join(ROOT, 'dockerfiles', img.split(':')[1])
    os.makedirs(tdir, exist_ok=True)
    with open(os.path.join(tdir, 'Dockerfile'), 'w') as f:
        f.write(tpl)


