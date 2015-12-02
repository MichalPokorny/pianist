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

"""Keyboard Status Monitor.
Monitors one or more keyboards and mouses.
Shows their status graphically.
"""

__author__ = 'Scott Kirkwood (scott+keymon@forusers.com)'
__version__ = '1.17'

import logging
import pygtk
pygtk.require('2.0')
import gobject
import gtk
import sys
import time
try:
  import xlib
except ImportError:
  print 'Error: Missing xlib, run sudo apt-get install python-xlib'
  sys.exit(-1)

import options
import mod_mapper
import settings

from ConfigParser import SafeConfigParser

class KeyMon:
  def __init__(self, options):
    """Options dict:
      meta: boolean show the meta (windows key)
      kbd_file: string Use the kbd file given.
    """
    self.btns = ['MOUSE', 'BTN_RIGHT', 'BTN_MIDDLE', 'BTN_MIDDLERIGHT',
                 'BTN_LEFT', 'BTN_LEFTRIGHT', 'BTN_LEFTMIDDLE',
                 'BTN_LEFTMIDDLERIGHT']
    self.options = options

    self.MODS = ['SHIFT', 'CTRL', 'META', 'ALT']

    self.options.kbd_files = settings.get_kbd_files()
    self.modmap = mod_mapper.safely_read_mod_map(self.options.kbd_file, self.options.kbd_files)

    self.devices = xlib.XEvents()
    self.devices.start()

    path = '/tmp/prvak-log-%s' % time.strftime('%Y%m%d-%H%M%S', time.gmtime())
    print 'Logging into: %s' % path
    self.event_log = open(path, 'w')

    self.add_events()

  def get_option(self, attr):
    """Shorthand for getattr(self.options, attr)"""
    return getattr(self.options, attr)

  def add_events(self):
    """Add events for the window to listen to."""
    gobject.idle_add(self.on_idle)

  def pointer_leave(self, unused_widget, unused_evt):

    self.set_accept_focus(False)

  def on_idle(self):
    """Check for events on idle."""
    event = self.devices.next_event()
    try:
      if event:
        self.handle_event(event)
      time.sleep(0.001)
    except KeyboardInterrupt:
      self.quit_program()
      return False
    return True  # continue calling

  def _log_event(self, event):
    self.event_log.write('%.5f;%s;%s;%s\n' % (
        time.time(), event.type, event.code, event.value))
    self.event_log.flush()

  def handle_event(self, event):
    """Handle an X event."""

    self._log_event(event)

  def quit_program(self, *unused_args):
    """Quit the program."""
    self.devices.stop_listening()
    self.destroy(None)

  def destroy(self, unused_widget, unused_data=None):
    """Also quit the program."""
    self.devices.stop_listening()
    gtk.main_quit()

def create_options():
  opts = options.Options()

  opts.add_option(opt_long='--only_combo', dest='only_combo', type='bool',
                  default=False,
                  help='Show only key combos (ex. Control-A)')
  opts.add_option(opt_long='--sticky', dest='sticky_mode', type='bool',
                  default=False,
                  help='Sticky mode')
  opts.add_option(opt_long='--kbdfile', dest='kbd_file',
                  default=None,
                  help='Use this kbd filename.')

  opts.add_option(opt_short=None, opt_long=None, type='int',
                  dest='x_pos', default=-1, help='Last X Position')
  opts.add_option(opt_short=None, opt_long=None, type='int',
                  dest='y_pos', default=-1, help='Last Y Position')

  opts.add_option(opt_long='--loglevel', dest='loglevel', type='str', default='',
                  help='Logging level')
  opts.add_option(opt_short='-d', opt_long='--debug', dest='debug', type='bool',
                  default=False,
                  help='Output debugging information. '
                         'Shorthand for --loglevel=debug')
  return opts


def main():
  """Run the program."""
  # Check for --loglevel, --debug, we deal with them by ourselves because
  # option parser also use logging.
  loglevel = None
  for idx, arg in enumerate(sys.argv):
    if '--loglevel' in arg:
      if '=' in arg:
        loglevel = arg.split('=')[1]
      else:
        loglevel = sys.argv[idx + 1]
      level = getattr(logging, loglevel.upper(), None)
      if level is None:
          raise ValueError('Invalid log level: %s' % loglevel)
      loglevel = level
  else:
    if '--debug' in sys.argv or '-d' in sys.argv:
      loglevel = logging.DEBUG
  logging.basicConfig(
      level=loglevel,
      format='%(filename)s [%(lineno)d]: %(levelname)s %(message)s')
  if loglevel is None:
    # Disabling warning, info, debug messages
    logging.disable(logging.WARNING)

  opts = create_options()
  desc = 'Usage: %prog [Options...]'
  opts.parse_args(desc, sys.argv)

  keymon = KeyMon(opts)
  try:
    gtk.main()
  except KeyboardInterrupt:
    keymon.quit_program()

if __name__ == '__main__':
  #import cProfile
  #cProfile.run('main()', 'keymonprof')
  main()
