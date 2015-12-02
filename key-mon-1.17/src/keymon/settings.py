#!/usr/bin/python
#
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Settings dialog and related functions."""

__author__ = 'scott@forusers.com (Scott Kirkwood)'

import gettext
import gobject
import gtk
import logging
import os

from ConfigParser import SafeConfigParser

LOG = logging.getLogger('settings')


def get_config_dir():
  """Return the base directory of configuration."""
  return os.environ.get('XDG_CONFIG_HOME',
                        os.path.expanduser('~/.config')) + '/key-mon'

def get_config_dirs(kind):
  """Return search paths of certain kind of configuration directory.
  Args:
    kind: Subfolder name
  Return:
    List of full paths
  """
  config_dirs = [d for d in (
              os.path.join(get_config_dir(), kind),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), kind)) \
          if os.path.exists(d)]
  return config_dirs

def get_kbd_files():
  """Return a list of kbd file paths"""
  config_dirs = get_config_dirs('')
  kbd_files = [
      os.path.join(d, f) \
      for d in config_dirs \
      for f in sorted(os.listdir(d)) if f.endswith('.kbd')]
  return kbd_files
