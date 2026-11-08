"""Build/release regression contracts; run with python3 -m unittest discover -s tests."""
from pathlib import Path
import json
import subprocess
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class BuildSafetyTests(unittest.TestCase):
    def test_build_and_qemu_use_identical_candidate_source(self):
        workflow = yaml.load((ROOT / '.github/workflows/prerelease.yml').read_text(), Loader=yaml.BaseLoader)
        build = workflow['jobs']['build']
        checkout = next(s for s in build['steps'] if s.get('uses', '').startswith('actions/checkout@'))
        expected = '${{ github.event.pull_request.head.sha || github.sha }}'
        self.assertEqual(checkout.get('with', {}).get('ref'), expected)
        image_step = next(s for s in build['steps'] if s.get('id') == 'images')
        self.assertEqual(image_step['env']['HEAD_SHA'], expected)
        self.assertEqual(workflow['jobs']['qemu']['with']['repo_ref'], expected)

    def test_promotion_requires_explicit_main_dispatch(self):
        workflow = yaml.load((ROOT / '.github/workflows/prerelease.yml').read_text(), Loader=yaml.BaseLoader)
        triggers = workflow['on']
        self.assertNotIn('paths', triggers['push'])
        self.assertEqual(triggers['push']['branches'], ['main'])
        publish_input = triggers.get('workflow_dispatch', {}).get('inputs', {}).get('publish', {})
        self.assertEqual(publish_input.get('type'), 'boolean')
        self.assertEqual(publish_input.get('default'), 'false')
        condition = workflow['jobs']['publish']['if']
        for event in ('push', 'pull_request', 'workflow_dispatch'):
            for ref in ('refs/heads/main', 'refs/heads/feature'):
                for publish in (False, True):
                    expression = condition.removeprefix('${{').removesuffix('}}').strip()
                    for name, value in {'github.event_name': event, 'github.ref': ref, 'inputs.publish': publish}.items():
                        expression = expression.replace(name, repr(value))
                    result = eval(expression.replace('&&', ' and ').replace('||', ' or '), {'__builtins__': {}})
                    self.assertEqual(result, event == 'workflow_dispatch' and ref == 'refs/heads/main' and publish,
                                     (event, ref, publish))
        promotion = workflow['jobs']['publish']['steps'][-1]['run']
        stable_input = triggers['workflow_dispatch']['inputs'].get('stable', {})
        self.assertEqual(stable_input.get('type'), 'boolean')
        self.assertEqual(stable_input.get('default'), 'false')
        self.assertIn('--prerelease', promotion)
        self.assertIn('--latest', promotion)
        self.assertIn('"$STABLE" == true', promotion)
        self.assertIn('Refusing to overwrite', promotion)
        self.assertIn('grep -qiE', promotion)
        self.assertIn('skopeo copy --preserve-digests', promotion)

    def test_forks_only_run_read_only_local_validation(self):
        workflow = yaml.load((ROOT / '.github/workflows/prerelease.yml').read_text(), Loader=yaml.BaseLoader)
        build = workflow['jobs']['build']
        condition = build.get('if', '${{ True }}')
        for event, head_repo, expected in [('push', '', True), ('workflow_dispatch', '', True),
                                           ('pull_request', 'owner/module', True),
                                           ('pull_request', 'outsider/module', False)]:
            expression = condition.removeprefix('${{').removesuffix('}}').strip()
            for name, value in {'github.event.pull_request.head.repo.full_name': head_repo,
                                'github.event_name': event, 'github.repository': 'owner/module'}.items():
                expression = expression.replace(name, repr(value))
            self.assertEqual(eval(expression.replace('&&', ' and ').replace('||', ' or '), {'__builtins__': {}}), expected)
        local = workflow['jobs']['validate']
        self.assertNotIn('if', local)
        self.assertEqual(local['permissions'], {'contents': 'read'})
        commands = '\n'.join(s.get('run', '') for s in local['steps'])
        self.assertIn('bash -n build-images.sh', commands)
        self.assertIn('python3 -m unittest discover -s tests', commands)
        self.assertIn('REPOBASE=localhost/traefik-validation bash build-images.sh', commands)
        self.assertNotRegex(commands, r'\b(login|push)\b')
        self.assertIn('validate', build['needs'])
        self.assertIn('build', workflow['jobs']['qemu']['needs'])

    def test_module_sources_have_valid_syntax(self):
        checked = 0
        for path in (ROOT / 'imageroot').rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            content = path.read_bytes()
            first = content.split(b'\n', 1)[0]
            with self.subTest(path=str(path.relative_to(ROOT))):
                if path.suffix == '.py' or (first.startswith(b'#!') and b'python' in first):
                    compile(content, str(path), 'exec')
                elif path.suffix == '.json':
                    json.loads(content)
                elif path.suffix == '.sh' or (first.startswith(b'#!') and b'sh' in first):
                    subprocess.run(['bash', '-n', str(path)], check=True, capture_output=True)
                else:
                    continue
                checked += 1
        self.assertGreater(checked, 0, 'Syntax validation must not silently check nothing')

    def test_runtime_is_pinned_to_verified_multiarch_index(self):
        script = (ROOT / 'build-images.sh').read_text()
        self.assertIn('docker.io/traefik@sha256:f4bb143d1135a579b630ed491e17ec50f6f7c9c6a30585ff3d385471d2a86f5a', script)
        self.assertNotRegex(script, r'org.nethserver.images=docker.io/traefik:v')


if __name__ == '__main__':
    unittest.main()
