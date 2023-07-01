import json
import os


class App(object):
    def __init__(self):
        self.run_complete = False
        self.is_spot = False
        self.is_yarn = False
        self.is_yarn_modern = False
        self.is_yarn_zero_install = False
        self.is_terminating = False
        self.specs_completed = set()

        # detect if spot
        if os.path.exists('/etc/podinfo/annotations'):
            self.detect_spot()

        with open('/etc/hostname') as f:
            self.hostname = f.read().strip()

    def detect_spot(self):
        with open('/etc/podinfo/annotations', 'r') as f:
            for line in f.readlines():
                if line.startswith('autopilot.gke.io/selector-toleration'):
                    for tol in json.loads(json.loads(line.split('=')[1]))['outputTolerations']:
                        if tol['key'] == 'cloud.google.com/gke-spot':
                            self.is_spot = (tol['value'] == 'true')
                            return


app = App()
