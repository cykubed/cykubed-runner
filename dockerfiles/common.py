import os
from string import Template

NODE_MAJOR_VERSIONS = ['14'] #, '16', '18', '20']
BROWSERS = ['chrome', 'edge']#, 'firefox']
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
GENERATION_DIR = os.path.join(os.path.dirname(__file__), 'generated')
BASE_DOCKERFILE = os.path.join(os.path.dirname(__file__), 'base/Dockerfile')


def render(template_name, context, outputdir=None, output_file=None) -> str:
    template_file = os.path.join(TEMPLATE_DIR, template_name + '.tpl')
    with open(template_file, 'r') as f:
        s = Template(f.read()).substitute(context)

    if outputdir:
        ddir = os.path.join(GENERATION_DIR, outputdir)
        os.makedirs(ddir, exist_ok=True)
        with open(os.path.join(ddir, 'Dockerfile'), 'w') as f:
            f.write(s)
    elif output_file:
        ddir = os.path.join(GENERATION_DIR, os.path.dirname(output_file))
        if not os.path.exists(ddir):
            os.makedirs(ddir)
        with open(os.path.join(GENERATION_DIR, output_file), 'w') as f:
            f.write(s)
    return s.strip()