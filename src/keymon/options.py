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

"""Options Class for save, restoring and getting parameters from the command line.

This provides a class which handles both saving options to disk and gathering
options from the command line.

It behaves a little like optparse in that you can get or set the attributes by
name.
"""
__author__ = 'Scott Kirkwood (scott+keymon@forusers.com)'

import ConfigParser
import logging
import optparse
import os
import sys

LOG = logging.getLogger('options')

class OptionException(Exception):
  pass

class OptionItem(object):
  """Handles on option.
  It know both about optparse options and ConfigParser options.
  By setting opt_short, opt_long to None you won't create an optparse option.
  """
  def __init__(self, dest, _type, default, name, help,
      opt_group=None, opt_short=None, opt_long=None):
    """Create an option
    Args:
      dest: a unique name for this variable, used internally.
      _type: The data type.
      default: The default value if none given.
      name: the translated name.
      _help: Help text to show.
      opt_group: Optional option group
      opt_short: the short name of the option
      opt_long: the long name for the option
    """
    self._dirty = False
    self._value = None
    self._temp_value = None

    self._dest = dest
    self._type = _type
    self._default = default
    self._name = name
    self._help = help
    self._opt_group = opt_group
    self._opt_short = opt_short
    if self._opt_short and not self._opt_short.startswith('-'):
      raise OptionException('Invalid short option %s' % self._opt_short)
    self._opt_long = opt_long
    if self._opt_long and not self._opt_long.startswith('--'):
      raise OptionException('Invalid long option %r' % self._opt_long)
    if self._type not in ('int', 'float', 'bool', 'str'):
      raise OptionException('Unsupported type: %s' % self._type)
    self._set_value(default)

  def add_to_parser(self, parser):
    if not self._opt_short and not self._opt_long:
      return
    if self._type == 'bool':
      self._add_bool_to_parser(parser)
      return
    args = []
    if self._opt_short:
      args.append(self._opt_short)
    if self._opt_long:
      args.append(self._opt_long)
    parser.add_option(dest=self._dest, type=self._type, default=self._default,
       help=self._help, *args)

  def _add_bool_to_parser(self, parser):
    """Booleans need special handling."""
    args = []
    if self._opt_short:
      args.append(self._opt_short)
    if self._opt_long:
      args.append(self._opt_long)
    parser.add_option(action='store_true', default=self._default,
      dest=self._dest, help=self._help, *args)

  def set_from_optparse(self, opts, args):
    """Try and set an option from optparse.
    Args:
      opts: options as returned from parse_args()
      args: arguments as returned bys sys.args.
    """
    if not self._opt_short and not self._opt_long:
      return

    # Was this option actually passed on the command line?
    found = False
    if args:
      for arg in args:
        if self._type == 'bool' and arg.startswith('--no'):
          arg = '--' + arg[4:]
        # Remove the --x=123, if any
        arg = arg.split('=')[0]
        if arg == self._opt_short or arg == self._opt_long:
          found = True
          break

    if hasattr(opts, self._dest):
      opt_val = getattr(opts, self._dest)
      if found:
        self._set_temp_value(opt_val)

  def get_value(self):
    """Return the value."""
    if self._temp_value is not None:
      return self._temp_value
    return self._value

  def _set_attr_value(self, attr, val):
    """Set the value via attribute name.
    Args:
      attr: attribute name ('_value', or '_temp_value')
      val: value to set
    """
    old_val = getattr(self, attr)
    if val is None:
      setattr(self, attr, val)
    elif self._type == 'int':
      setattr(self, attr, int(val))
    elif self._type == 'float':
      setattr(self, attr, float(val))
    elif self._type == 'bool':
      if isinstance(val, basestring):
        if val.lower() in ('false', 'off', 'no', '0'):
          setattr(self, attr, False)
        elif val.lower() in ('true', 'on', 'yes', '1'):
          setattr(self, attr, True)
        else:
          raise OptionException('Unable to convert %s to bool' % val)
      else:
        setattr(self, attr, bool(val))
    else:
      setattr(self, attr, val)
    self._dirty = old_val != getattr(self, attr)

  def _set_value(self, val):
    self._set_attr_value('_value', val)
    self._set_attr_value('_temp_value', None)

  def _set_temp_value(self, val):
    self._set_attr_value('_temp_value', val)

  value = property(get_value, _set_value, doc="Value")

  @property
  def dest(self):
    """Destination variable name."""
    return self._dest

  @property
  def name(self):
    """Localized name of the option."""
    return self._name

  @property
  def help(self):
    """Long description of the option."""
    return self._help

  @property
  def type(self):
    """String name of the type."""
    return self._type

  @property
  def opt_group(self):
    """Option group, if any."""
    return self._opt_group

  @property
  def opt_short(self):
    """Short option property (ex. '-v')."""
    return self._opt_short

  @property
  def opt_long(self):
    """Long option property (ex. '--verbose')."""
    return self._opt_long


class Options(object):
  """Store the options in memory, also saves to dist and creates opt_parser."""
  def __init__(self):
    self._options = {}
    self._opt_group = None
    self._opt_group_desc = {}
    self._options_order = []

  def __getattr__(self, name):
    if name not in self.__dict__['_options']:
      raise AttributeError('Invalid attribute name: %r' % name)
    return self._options[name].value

  def __setattr__(self, name, value):
    if name == '_options' or name not in self.__dict__['_options']:
      object.__setattr__(self, name, value)
    else:
      LOG.info('Setting %r = %r', name, value)
      self.__dict__['_options'][name].value = value

  def add_option_group(self, group, desc):
    self._opt_group = group
    self._opt_group_desc[group] = desc

  def add_option(self, dest, type='str', default=None, name=None, help=None,
      opt_short=None, opt_long=None):
    """Create an option
    Args:
      dest: a unique name for this variable, used internally.
      type: The data type.
      default: The default value if none given.
      name: the translated name.
      help: Help text to show.
      opt_group: the name of the option group or None
      opt_short: the short name of the option
      opt_long: the long name for the option
    """
    if dest in self._options:
      raise OptionException('Options %s already added' % dest)

    self._options_order.append(dest)
    self._options[dest] = OptionItem(dest, type, default,
        name, help,
        opt_group=self._opt_group, opt_short=opt_short, opt_long=opt_long)

  def parse_args(self, desc, args=None):
    """Add the options to the optparse instance and parse command line
    Args:
      desc: Description to use for the program.
      args: Args for testing or sys.args[1:] otherwise
    """
    parser = optparse.OptionParser(desc)
    for dest in self._options_order:
      opt = self._options[dest]
      opt.add_to_parser(parser)

    self._opt_ret, self._other_args = parser.parse_args(args)
    for opt in self._options.values():
      opt.set_from_optparse(self._opt_ret, args)
