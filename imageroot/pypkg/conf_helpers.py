#
# Copyright (C) 2025 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

import os
import re
import yaml

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
