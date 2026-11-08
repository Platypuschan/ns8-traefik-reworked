"""set-route/20writeconfig contracts with stubbed NS8 helpers; run with python3 -m unittest discover -s tests."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'imageroot/actions/set-route/20writeconfig'

STUBS = {
    'agent.py': 'statuses = []\n\ndef set_status(value):\n    statuses.append(value)\n',
    'cert_helpers.py': 'def update_redis_hosts_key_and_notify_event():\n    pass\n',
    'get_route.py': 'import json, os\n\ndef get_route(data, ignore_error=False):\n    return json.loads(os.environ.get("STUB_ROUTE", "{}"))\n',
}


def run_set_route(request, existing=None, other_configs=None):
    """Run the action in a scratch directory; return (returncode, stdout, stderr, written config)."""
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as stubs:
        for name, text in STUBS.items():
            Path(stubs, name).write_text(text)
        work = Path(tmp)
        (work / 'configs').mkdir()
        for name, config in (other_configs or {}).items():
            (work / 'configs' / name).write_text(yaml.safe_dump(config))
        runner = ('import runpy, sys; sys.path.insert(0, sys.argv[1]); '
                  'runpy.run_path(sys.argv[2], run_name="__main__")')
        env = dict(os.environ, AGENT_ID='module/traefik1', STUB_ROUTE=json.dumps(existing or {}))
        proc = subprocess.run([sys.executable, '-c', runner, stubs, str(SCRIPT)], input=json.dumps(request),
                              text=True, capture_output=True, cwd=work, env=env)
        written = work / 'configs' / f'{request["instance"]}.yml'
        config = yaml.safe_load(written.read_text()) if written.exists() else None
        return proc.returncode, proc.stdout, proc.stderr, config


class ClientCertificateTests(unittest.TestCase):
    base = {'instance': 'app1', 'url': 'http://127.0.0.1:2000', 'host': 'app.example.org', 'http2https': True}

    def test_client_certificate_middlewares_run_first(self):
        request = dict(self.base, client_certificates=True, ip_allowlist=['10.0.0.0/8'],
                       forward_auth={'address': 'http://127.0.0.1:9000/auth'})
        code, _, err, config = run_set_route(request)
        self.assertEqual(code, 0, err)
        router = config['http']['routers']['app1-https']
        self.assertEqual(router['tls']['options'], 'ns8-client-certificates@file')
        self.assertEqual(router['middlewares'][:2], ['app1-client-cert-clear', 'app1-client-cert-pass'])
        self.assertLess(router['middlewares'].index('app1-client-cert-pass'), router['middlewares'].index('app1-auth'))
        self.assertIn('ns8-client-certificates', config['tls']['options'])
        self.assertEqual(config['tls']['options']['ns8-client-certificates']['clientAuth']['clientAuthType'], 'RequestClientCert')

    def test_plain_route_has_no_client_certificate_configuration(self):
        code, _, err, config = run_set_route(self.base)
        self.assertEqual(code, 0, err)
        self.assertNotIn('options', config['http']['routers']['app1-https']['tls'])
        self.assertNotIn('tls', config)

    def test_requires_host_and_https_redirection_with_structured_error(self):
        for request in (dict(self.base, client_certificates=True, http2https=False),
                        {'instance': 'app1', 'url': 'http://127.0.0.1:2000', 'path': '/x', 'client_certificates': True}):
            code, out, _, config = run_set_route(request)
            self.assertEqual(code, 4)
            self.assertEqual(json.loads(out)[0]['error'], 'client_certificates_requires_host_and_http2https')
            self.assertIsNone(config, 'a rejected request must not write a configuration')

    def test_existing_setting_survives_update_without_the_field(self):
        existing = dict(self.base, client_certificates=True)
        code, _, err, config = run_set_route({'instance': 'app1', 'url': 'http://127.0.0.1:2001'}, existing=existing)
        self.assertEqual(code, 0, err)
        self.assertEqual(config['http']['routers']['app1-https']['tls']['options'], 'ns8-client-certificates@file')

    def test_conflicting_route_of_same_host_is_reported(self):
        other = {'http': {'routers': {'app0-https': {'rule': 'Host(`app.example.org`) && PathPrefix(`/a`)', 'tls': {}}}}}
        code, _, err, _ = run_set_route(dict(self.base, client_certificates=True), other_configs={'app0.yml': other})
        self.assertEqual(code, 0, err)
        self.assertIn('app0-https', err)
        code, _, err, _ = run_set_route(self.base, other_configs={'app0.yml': other})
        self.assertNotIn('WARNING', err)


if __name__ == '__main__':
    unittest.main()
