#
# Copyright (C) 2025 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

import agent
import sys
import os
import yaml
import json
import time
import glob
import subprocess
import datetime
import select
import re
import base64
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import signal
import atexit
import fcntl

_lock_default_certificate_done = False

def extract_certified_names(cert_data : bytearray) -> set:
    """
    Extract the subject common name and subject alternative names (SAN)
    from a PEM certificate.

    :param cert_data: Certificate, PEM-encoded.
    :return: A set of certified host names.
    """
    cert = x509.load_pem_x509_certificate(cert_data, default_backend())
    hostnames = set()
    # Extract Common Name (CN) from the Subject field
    subject = cert.subject
    cn = subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
    if cn:
        hostnames.add(cn[0].value)
    # Extract Subject Alternative Names (SANs), if any
    try:
        ext = cert.extensions.get_extension_for_oid(x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        san = ext.value
        hostnames.update(san.get_values_for_type(x509.DNSName))
    except x509.ExtensionNotFound:
        pass
    return set(map(str.lower, hostnames)) # lowercase names

def read_default_cert_names():
    """Return the list of host names configured in the
    defaultGeneratedCert section."""
    conf = parse_yaml_config('configs/_default_cert.yml')
    try:
        main = [conf['tls']['stores']['default']['defaultGeneratedCert']['domain']['main']]
    except KeyError:
        main = []
    try:
        sans = conf['tls']['stores']['default']['defaultGeneratedCert']['domain']['sans']
    except KeyError:
        sans = []
    return list(map(str.lower, main + sans)) # lowercase names

def read_custom_cert_names():
    """Return the list of main hostnames provided by custom/uploaded
    certificates."""
    main_hostnames = list()
    for cert_path in glob.glob("custom_certificates/*.crt"):
        hostname = cert_path.removeprefix("custom_certificates/").removesuffix(".crt")
        main_hostnames.append(hostname)
    return main_hostnames

def read_host_names_of_traefik_routers(only_http_routes=False) -> set:
    """Parse Traefik router configurations and extract the ACME certificate names."""
    router_names = set()
    host_pattern = re.compile(r'Host\(`(.*?)`\)', re.IGNORECASE)
    for cfgpath in glob.glob("configs/*.yml"):
        if cfgpath.startswith("configs/_"):
            continue # skip builtin files
        ocfg = parse_yaml_config(cfgpath)
        for rkey, orouter in ocfg.get('http', {}).get('routers', {}).items():
            if only_http_routes and not rkey.endswith('-https'):
                continue # the router does not belong to an HTTP route, ignore it
            rule_hosts = re.findall(host_pattern, orouter['rule'])
            for ktls in orouter.get('tls', {}):
                # case-insensitive key/value match in Traefik tls configuration:
                if ktls.lower() == 'certresolver' and orouter['tls'][ktls].lower() == 'acmeserver':
                    router_names.update(rule_hosts)
    return set(map(str.lower, router_names)) # lowercase names

def remove_custom_cert_by_path(path: str) -> set:
    """Remove the custom/uploaded certificate files and its Traefik
    configuration.

    :param path: certificate path
    :return: set of names certified by the removed certificate
    """
    cert_name = path.removeprefix("custom_certificates/").removesuffix(".crt")
    if cert_name in read_custom_cert_names():
        try:
            with open(f"custom_certificates/{cert_name}.crt", 'rb') as f:
                bcert = f.read()
            old_names = extract_certified_names(bcert)
        except FileNotFoundError:
            old_names = {cert_name}
        for path in [
            f"custom_certificates/{cert_name}.crt",
            f"custom_certificates/{cert_name}.key",
            f"configs/certificate_{cert_name}.yml",
        ]:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
        rdb = agent.redis_connect(privileged=True)
        rdb.delete(f'module/{os.environ["MODULE_ID"]}/certificate/{cert_name}')
        return old_names
    else:
        print(agent.SD_WARNING + f"Certificate {path} not found", file=sys.stderr)
        return set()

def has_acmejson_name(name: str) -> bool:
    """Return True if a certificate for name is found among acme.json
    Certificates."""
    name = name.lower()
    for dcert in list_internal_certificates(with_details=False):
        if name in dcert['traefik_names']:
            return True
    return False

def has_acmejson_cert(names: set, issubset: bool=False) -> bool:
    """Return True if a certificate for the exact set of names is found
    among acme.json Certificates."""
    names = set(map(str.lower, names)) # lowercase names
    for dcert in list_internal_certificates(with_details=False):
        if issubset and set(dcert['traefik_names']) >= names:
            return True
        elif set(dcert['traefik_names']) == names:
            return True
    return False

def wait_acmejson_sync(timeout=120, interval=2.1, names=[], issubset=False):
    """Poll the acme.json file every 'interval' seconds, until a
    certificate matching 'names' appears, an error occurs, or timeout
    seconds are elapsed. If list 'names' is given, it is expected to match
    a certficate set of names in acme.json. If not, this function waits
    for a certificate as configured in _default_cert.yml."""
    if not names:
        # Wait for the default certificate.
        names = read_default_cert_names()
    if not names:
        return True # Consider as obtained, if no names are set.
    elapsed = 0.0
    tstart = datetime.datetime.now(datetime.UTC)
    logcli_cmd = [
        "logcli",
        "query",
        "--tail",
        "--limit=1",
        "--from=" + tstart.isoformat(),
        "--timezone=Local", # use system timezone for output
        "--quiet",
        "--no-labels",
        '{module_id=~"traefik.+"} | json | line_format "{{.MESSAGE}}"' + \
        '| logfmt | providerName="acmeServer.acme" and error!=""' + \
        '| line_format "{{.error}}"',
    ]
    obtained = False
    with subprocess.Popen(logcli_cmd, stdout=subprocess.PIPE, text=True) as logcli_proc:
        fdmon = logcli_proc.stdout.fileno()
        while True:
            time.sleep(interval)
            elapsed += interval
            if elapsed >= timeout:
                print(agent.SD_ERR + f"Timeout after about {timeout} seconds. Certificate not obtained for {names}.", file=sys.stderr)
                obtained = False
                break
            if has_acmejson_cert(set(names), issubset):
                obtained = True # certificate obtained successfully!
                break
            read_fds, _, _ = select.select([fdmon], [], [], 0) # 0 = non blocking
            if read_fds:
                obtained = False
                break # got some error messages from logcli.
        logcli_proc.terminate()
    return obtained

def set_default_certificate(names: list):
    """Overwrite default certificate configuration to use an internal (acme.json) certificate
    with main name and sans."""
    names = list(map(str.lower, names)) # lowercase names
    tlsconf = parse_yaml_config("configs/_default_cert.yml")
    defstore = tlsconf['tls']['stores']['default']
    if 'defaultCertificate' in defstore:
        # Remove self-signed cert config.
        del defstore['defaultCertificate']
    defstore['defaultGeneratedCert'] = {
        'resolver': 'acmeServer',
        'domain': {
            'main': names[0],
            'sans': names[1:],
        },
    }
    write_yaml_config(tlsconf, 'configs/_default_cert.yml')

def add_default_certificate_name(main, sans=[]):
    """Add 'main' and 'sans' to the current certificate configuration. If
    the current certificate is already configured, 'main' is added as SAN,
    otherwise it is used to initialize a new defaultGeneratedCert
    configuration."""
    main = main.lower()
    sans = list(map(str.lower, sans)) # lowercase names
    tlsconf = parse_yaml_config("configs/_default_cert.yml")
    defstore = tlsconf['tls']['stores']['default']
    if 'defaultCertificate' in defstore:
        # Remove self-signed cert config.
        del defstore['defaultCertificate']
        # Initialize config for ACME.
        defstore['defaultGeneratedCert'] = {
            'resolver': 'acmeServer',
            'domain': {
                'main': main,
                'sans': sans,
            },
        }
    elif 'defaultGeneratedCert' in defstore:
        # ACME config already exists. Merge names from request into SANs of
        # defaultGeneratedCert.
        sans = set(defstore['defaultGeneratedCert']['domain']['sans'])
        sans.add(main)
        sans.update(set(sans))
        sans.discard(defstore['defaultGeneratedCert']['domain']['main'])
        defstore['defaultGeneratedCert']['domain']['sans'] = list(sans)
    write_yaml_config(tlsconf, 'configs/_default_cert.yml')

def reset_selfsigned_certificate():
    """Replaces the default certificate configuration, restoring the
    config for the self-signed one."""
    tlsconf = {
        "tls": {
            "stores": {
                "default": {
                    "defaultCertificate": {
                        "certFile": "/etc/traefik/selfsigned.crt",
                        "keyFile": "/etc/traefik/selfsigned.key",
                    }
                }
            }
        }
    }
    write_yaml_config(tlsconf, 'configs/_default_cert.yml')

def write_yaml_config(conf, path):
    """Safely write a configuration file."""
    with open(path + '.tmp', 'w') as fp:
        fp.write(yaml.safe_dump(conf, default_flow_style=False, sort_keys=False, allow_unicode=True))
    os.rename(path + '.tmp', path)

def parse_yaml_config(path):
    """Parse a YAML configuration file."""
    with open(path, 'r') as fp:
        conf = yaml.safe_load(fp)
    return conf

def traefik_last_acme_error_since(tstart):
    """Get the last Traefik error related to ACME from Loki.

    :param tstart: a ISO8601 string with TZ offset
    :return: string
    """
    try:
        acme_error = subprocess.check_output([
            "logcli",
            "query",
            "--limit=1",
            "--from=" + tstart.isoformat(),
            "--timezone=Local", # use system timezone for output
            "--quiet",
            "--no-labels",
            '{module_id=~"traefik.+"} | json | line_format "{{.MESSAGE}}"' + \
            '| logfmt | providerName="acmeServer.acme" and error!=""' + \
            '| line_format "{{.error}}"',
        ], timeout=15, text=True)
    except subprocess.TimeoutExpired as ex:
        acme_error = 'traefik_last_acme_error_since(): logcli timeout - ' + str(ex)
    except subprocess.CalledProcessError as ex:
        acme_error = 'traefik_last_acme_error_since(): logcli error - ' + str(ex)
    return acme_error

def validate_certificate_names(main, sans=[], timeout=60):
    """Issue a certificate request to ACME server and return if it has
    been obtained or not."""
    # Check if we already have the same certificate in acme.json:
    if has_acmejson_cert(set([main] + sans), issubset=True):
        return True
    uniqconf = f"_validation{os.getpid()}"
    routerconf = {
        "http": {
            "services": {
                uniqconf: {
                    "loadBalancer": {
                        "servers": ["ping@internal"]
                    }
                }
            },
            "routers": {
                uniqconf: {
                    "rule": f"Host(`{main}`) && Path(`/{uniqconf}`)",
                    "priority": 100001,
                    "service": uniqconf,
                    "entryPoints": ["https"],
                    "tls": {
                        "domains": [{"main": main, "sans": sans}],
                        "certResolver": "acmeServer",
                    }
                }
            }
        }
    }
    _register_tempfile_cleanup(f"configs/{uniqconf}.yml")
    write_yaml_config(routerconf, f"configs/{uniqconf}.yml")
    obtained = wait_acmejson_sync(timeout=timeout, interval=1.1, names=[main] + sans, issubset=True)
    os.unlink(f"configs/{uniqconf}.yml")
    return obtained

def _register_tempfile_cleanup(tpath: str):
    def _fcleanup(*_):
        try:
            os.unlink(tpath)
        except FileNotFoundError:
            pass
    if not callable(signal.getsignal(signal.SIGTERM)):
        atexit.register(_fcleanup)
        signal.signal(signal.SIGTERM, _fcleanup)

def purge_acme_json_and_restart_traefik(purge_serial: str="", purge_names: set={}, purge_obsolete: bool=False) -> set:
    """Lookup and delete acme.json certificates matching purge_serial or
    purge_names. Use at most one argument."""
    try:
        with open('acme/acme.json', 'r') as fp:
            acmejson = json.load(fp)
        acmecerts = acmejson['acmeServer']["Certificates"] or []
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return set() # nothing has been purged
    purge_names = set(map(str.lower, purge_names)) # lowercase names
    removed_names = set()
    preserved_certificates = []
    names_of_traefik_routers = read_host_names_of_traefik_routers()
    default_cert_names = set(read_default_cert_names())
    for ocert in acmecerts:
        bcert = base64.b64decode(ocert["certificate"])
        dcert = extract_certificate_attributes(bcert)
        certificate_names = set(dcert['names'])
        if purge_serial:
            if dcert['serial'] == purge_serial:
                removed_names.update(certificate_names)
            else:
                preserved_certificates.append(ocert)
        elif purge_names:
            if purge_names == certificate_names:
                removed_names.update(certificate_names)
            else:
                preserved_certificates.append(ocert)
        elif purge_obsolete:
            if (certificate_names != default_cert_names
                and not certificate_names.issubset(names_of_traefik_routers)):
                # Obsolete certificate found
                removed_names.update(certificate_names)
            else:
                preserved_certificates.append(ocert)
        else:
            return set() # nothing to do
    if not removed_names:
        return set() # nothing has been purged
    default_cert_names = set(read_default_cert_names())
    if default_cert_names == removed_names:
        reset_selfsigned_certificate()
    #
    # Write the new acme.json file and restart Traefik
    #
    acmejson['acmeServer']["Certificates"][:] = preserved_certificates
    tmpmask = os.umask(0o177) # Restrict new file permissions to 0600
    with open('acme/acme.json.tmp', 'w') as tmpfp:
        json.dump(acmejson, fp=tmpfp)
    os.rename('acme/acme.json.tmp', 'acme/acme.json')
    os.umask(tmpmask) # Restore previous mask
    agent.run_helper("systemctl", "--user", "restart", "traefik")
    return removed_names

def clear_certresolver_in_http_routes(for_names: set):
    """Scan HTTP routes configuration files and disable ACME certResolver
    if its Host rules match the given for_names set."""
    for_names = set(map(str.lower, for_names)) # lowercase names
    route_names = set()
    host_pattern = re.compile(r'Host\(`(.*?)`\)', re.IGNORECASE)
    for cfgpath in glob.glob("configs/*.yml"):
        if cfgpath.startswith("configs/_"):
            continue # skip builtin files
        ocfg = parse_yaml_config(cfgpath)
        ocfg_changed = False
        for krouter in ocfg.get('http', {}).get('routers', {}):
            orouter = ocfg['http']['routers'][krouter]
            rule_hosts = set(map(str.lower, re.findall(host_pattern, orouter.get('rule', ""))))
            try:
                # Case-insensitive key/value match in Traefik tls configuration:
                for ktls in list(orouter['tls']):
                    if (ktls.lower() == 'certresolver'
                        and orouter['tls'][ktls].lower() == 'acmeserver'
                        and for_names.intersection(rule_hosts)):
                        # name match, disable ACME certResolver
                        del orouter['tls'][ktls]
                        ocfg_changed = True
            except KeyError:
                pass
        if ocfg_changed:
            print('Clear ACME certResolver in', cfgpath, file=sys.stderr)
            write_yaml_config(ocfg, cfgpath)

def extract_certificate_attributes(cert_data : bytearray) -> dict:
    """
    Extract the certificate attributes from a PEM certificate.

    :param cert_data: Certificate, PEM-encoded.
    :return: A dict of attributes
    """
    def x509_name_to_string(oname):
        # Extract Common Name (CN) from the given oname:
        cn = oname.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
        if cn:
            return cn[0].value # CN found, use it
        else:
            return None

    cert = x509.load_pem_x509_certificate(cert_data, default_backend())
    hostnames = set()
    main_name = x509_name_to_string(cert.subject)
    if main_name:
        hostnames.add(main_name)
    # Extract Subject Alternative Names (SANs), if any
    try:
        ext = cert.extensions.get_extension_for_oid(x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        san = ext.value
        hostnames.update(san.get_values_for_type(x509.DNSName))
    except x509.ExtensionNotFound:
        pass

    return {
        "names": sorted(hostnames),
        "subject": x509_name_to_string(cert.subject) or cert.subject.rfc4514_string(),
        "issuer": cert.issuer.rfc4514_string(),
        "serial": str(cert.serial_number),
        "valid_to": cert.not_valid_after.replace(tzinfo=datetime.timezone.utc),
        "valid_from": cert.not_valid_before.replace(tzinfo=datetime.timezone.utc),
    }

def list_internal_certificates(acmejson_path: str='acme/acme.json', with_details: bool=True) -> list:
    """Parse acme.json and extract the list certificates with X.509
    detailed attributes. With option with_details=False, only the
    certificate names assigned by Traefik are extracted."""
    try:
        if os.path.getsize(acmejson_path) == 0:
            return []
        with open(acmejson_path, 'r') as fp:
            acmejson = json.load(fp)
        acmecerts = acmejson['acmeServer']["Certificates"] or []
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as ex:
        print(agent.SD_WARNING + f"Failed to parse JSON file {acmejson_path}:", ex, file=sys.stderr)
        return []
    certificates = []
    for ocert in acmecerts:
        if 'certificate' in ocert:
            dcert = {
                "traefik_names": [ocert['domain']['main']] + ocert['domain'].get('sans', [])
            }
            if with_details:
                bcert = base64.b64decode(ocert["certificate"])
                dcert.update(extract_certificate_attributes(bcert))
            certificates.append(dcert)
    return certificates

def list_custom_certificates():
    certificates = []
    for cert_path in glob.glob("custom_certificates/*.crt"):
        try:
            with open(cert_path, 'rb') as fp:
                dcert = extract_certificate_attributes(fp.read())
            dcert['path'] = cert_path
            certificates.append(dcert)
        except Exception as ex:
            print(agent.SD_WARNING + "Failed to parse certificate", cert_path, ":", ex, file=sys.stderr)
    return certificates

def _lock_default_certificate():
    """
    Acquire an exclusive blocking lock for the default certificate configuration.
    The lock is released when the calling process terminates.
    Equivalent to: flock -x <file>
    """
    global _lock_default_certificate_done
    if not _lock_default_certificate_done:
        _lock_default_certificate_done = True
    else:
        print(agent.SD_WARNING + "NOOP: the default-certificate lock was already requested by current process.", file=sys.stderr)
        return
    fd = os.open(".default-certificate.lock", os.O_RDWR | os.O_CREAT, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX)  # blocking exclusive lock

def request_new_default_certificate(new_cert_names:list, merge_names:bool=False, sync_timeout:int=60) -> (bool, str):
    """Request an ACME certificate with new_cert_names, and set is as
    Traefik's default certificate."""
    _lock_default_certificate()
    new_cert_names = list(map(str.lower, new_cert_names)) # lowercase names
    cur_cert_names = read_default_cert_names()
    if merge_names == True:
        new_cert_names = cur_cert_names + new_cert_names
    # Before issuing a new ACME request, check if we have the certificate
    # in the internal storage:
    if has_acmejson_cert(set(new_cert_names)):
        if set(new_cert_names) == set(cur_cert_names):
            return (True, "") # The wanted certificate was already obtained and configured. Nothing to do.
        else:
            # the wanted certificate was already obtained. Configure it as default.
            set_default_certificate(new_cert_names)
    # To force a new ACME request we overwrite _default.yml.
    tstart = datetime.datetime.now(datetime.UTC)
    set_default_certificate(new_cert_names)
    obtained = wait_acmejson_sync(names=new_cert_names, timeout=sync_timeout, interval=1.1, issubset=False)
    acme_error = ""
    if obtained:
        # Notify hosts-changed event
        update_redis_hosts_key_and_notify_event()
    else:
        # Rollback configuration:
        if cur_cert_names:
            set_default_certificate(cur_cert_names)
        else:
            reset_selfsigned_certificate()
        acme_error = traefik_last_acme_error_since(tstart)
    return (obtained, acme_error)

def request_new_certificate(new_cert_names:list, sync_timeout:int=60) -> (bool, str):
    """Request an ACME certificate with new_cert_names, by configuring a temporary Traefik router."""
    # Before issuing a new ACME request, check if we have the certificate
    # in the internal storage:
    if has_acmejson_cert(set(new_cert_names)):
        return (True, "")
    tstart = datetime.datetime.now(datetime.UTC)
    obtained = validate_certificate_names(main=new_cert_names[0], sans=new_cert_names[1:], timeout=sync_timeout)
    acme_error = ""
    if not obtained:
        acme_error = traefik_last_acme_error_since(tstart)
    return (obtained, acme_error)

def update_redis_hosts_key_and_notify_event():
    """Extract host names from HTTP routes and the default certificate and
    notify hosts-changed event with collected names."""
    route_names = set()
    host_pattern = re.compile(r'Host\(`(.*?)`\)')
    for cfgpath in glob.glob("configs/*.yml"):
        if cfgpath.startswith("configs/_"):
            continue # skip builtin files
        ocfg = parse_yaml_config(cfgpath)
        for orouter in ocfg.get('http', {}).get('routers', {}).values():
            rule_hosts = set(map(str.lower, re.findall(host_pattern, orouter['rule'])))
            route_names.update(rule_hosts)
    route_names.update(set(read_default_cert_names()))
    agent_id = os.environ["AGENT_ID"]
    wrdb = agent.redis_connect(privileged=True)
    current_hosts = set(map(str.lower, wrdb.smembers(f'{agent_id}/hosts')))
    if current_hosts != route_names:
        # Write pipeline to redis
        trx = wrdb.pipeline()
        trx.delete(f'{agent_id}/hosts')
        if route_names:
            trx.sadd(f'{agent_id}/hosts', *list(route_names))
        trx.publish(f'{agent_id}/event/hosts-changed', json.dumps({'node_id': os.environ['NODE_ID']}))
        trx.execute()
