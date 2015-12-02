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

import locale
import logging
import pygtk
pygtk.require('2.0')
import gettext
import gobject
import gtk
import os
import sys
import time
try:
  import xlib
except ImportError:
  print 'Error: Missing xlib, run sudo apt-get install python-xlib'
  sys.exit(-1)

import options
import lazy_pixbuf_creator
import mod_mapper
import settings
import shaped_window
import two_state_image

from ConfigParser import SafeConfigParser

gettext.install('key-mon', 'locale')


def fix_svg_key_closure(fname, from_tos):
  """Create a closure to modify the key.
  Args:
    from_tos: list of from, to pairs for search replace.
  Returns:
    A bound function which returns the file fname with modifications.
  """

  def fix_svg_key():
    """Given an SVG file return the SVG text fixed."""
    logging.debug('Read file %r', fname)
    fin = open(fname)
    fbytes = fin.read()
    fin.close()
    for fin, t in from_tos:
      # Quick XML escape fix
      t = t.replace('<', '&lt;')
      fbytes = fbytes.replace(fin, t)
    return fbytes

  return fix_svg_key


def cstrf(func):
  """Change locale before using str function"""
  OLD_CTYPE = locale.getlocale(locale.LC_CTYPE)
  locale.setlocale(locale.LC_CTYPE, 'C')
  s = func()
  locale.setlocale(locale.LC_CTYPE, OLD_CTYPE)
  return s


class KeyMon:
  """main KeyMon window class."""

  def __init__(self, options):
    """Create the Key Mon window.
    Options dict:
      meta: boolean show the meta (windows key)
      kbd_file: string Use the kbd file given.
      theme: Name of the theme to use to draw keys
    """
    settings.SettingsDialog.register()
    self.btns = ['MOUSE', 'BTN_RIGHT', 'BTN_MIDDLE', 'BTN_MIDDLERIGHT',
                 'BTN_LEFT', 'BTN_LEFTRIGHT', 'BTN_LEFTMIDDLE',
                 'BTN_LEFTMIDDLERIGHT']
    self.options = options
    self.pathname = os.path.dirname(os.path.abspath(__file__))
    self.svg_size = ''
    # Make lint happy by defining these.
    self.hbox = None
    self.window = None
    self.event_box = None
    self.mouse_indicator_win = None

    self.no_press_timer = None

    self.move_dragged = False
    self.shape_mask_current = None
    self.shape_mask_cache = {}

    self.MODS = ['SHIFT', 'CTRL', 'META', 'ALT']


    self.options.kbd_files = settings.get_kbd_files()
    self.modmap = mod_mapper.safely_read_mod_map(self.options.kbd_file, self.options.kbd_files)

    self.name_fnames = self.create_names_to_fnames()
    self.devices = xlib.XEvents()
    self.devices.start()

    self.pixbufs = lazy_pixbuf_creator.LazyPixbufCreator(self.name_fnames)
    self.create_window()
    self.reset_no_press_timer()

    path = '/tmp/prvak-log-%s' % time.strftime('%Y%m%d-%H%M%S', time.gmtime())
    self.event_log = open(path, 'w')

  def get_option(self, attr):
    """Shorthand for getattr(self.options, attr)"""
    return getattr(self.options, attr)

  def create_names_to_fnames(self):
    """Give a name to images."""
    self.svg_size = ''
    ftn = {
      'MOUSE': [self.svg_name('mouse'),],
      'BTN_MIDDLE': [self.svg_name('mouse'), self.svg_name('middle-mouse')],
      'SCROLL_UP': [self.svg_name('mouse'), self.svg_name('scroll-up-mouse')],
      'SCROLL_DOWN': [self.svg_name('mouse'), self.svg_name('scroll-dn-mouse')],

      'REL_LEFT': [self.svg_name('mouse'), self.svg_name('sroll-lft-mouse')],
      'REL_RIGHT': [self.svg_name('mouse'), self.svg_name('scroll-rgt-mouse')],
      'SHIFT': [self.svg_name('shift')],
      'SHIFT_EMPTY': [self.svg_name('shift'), self.svg_name('whiteout-72')],
      'CTRL': [self.svg_name('ctrl')],
      'CTRL_EMPTY': [self.svg_name('ctrl'), self.svg_name('whiteout-58')],
      'META': [self.svg_name('meta'), self.svg_name('meta')],
      'META_EMPTY': [self.svg_name('meta'), self.svg_name('whiteout-58')],
      'ALT': [self.svg_name('alt')],
      'ALT_EMPTY': [self.svg_name('alt'), self.svg_name('whiteout-58')],
      'ALTGR': [self.svg_name('altgr')],
      'ALTGR_EMPTY': [self.svg_name('altgr'), self.svg_name('whiteout-58')],
      'KEY_EMPTY': [
          fix_svg_key_closure(self.svg_name('one-char-template'), [('&amp;', '')]),
              self.svg_name('whiteout-48')],
      'BTN_LEFTRIGHT': [
          self.svg_name('mouse'), self.svg_name('left-mouse'),
          self.svg_name('right-mouse')],
      'BTN_LEFTMIDDLERIGHT': [
          self.svg_name('mouse'), self.svg_name('left-mouse'),
          self.svg_name('middle-mouse'), self.svg_name('right-mouse')],
    }
    left_str = 'left'
    right_str = 'right'

    ftn.update({
      'BTN_RIGHT': [self.svg_name('mouse'),
        self.svg_name('%s-mouse' % right_str)],
      'BTN_LEFT': [self.svg_name('mouse'),
        self.svg_name('%s-mouse' % left_str)],
      'BTN_LEFTMIDDLE': [
          self.svg_name('mouse'), self.svg_name('%s-mouse' % left_str),
          self.svg_name('middle-mouse')],
      'BTN_MIDDLERIGHT': [
          self.svg_name('mouse'), self.svg_name('middle-mouse'),
          self.svg_name('%s-mouse' % right_str)],
    })

    ftn.update({
      'KEY_SPACE': [
          fix_svg_key_closure(self.svg_name('two-line-wide'),
          [('TOP', 'Space'), ('BOTTOM', '')])],
      'KEY_TAB': [
          fix_svg_key_closure(self.svg_name('two-line-wide'),
          [('TOP', 'Tab'), ('BOTTOM', u'\u21B9')])],
      'KEY_BACKSPACE': [
          fix_svg_key_closure(self.svg_name('two-line-wide'),
          [('TOP', 'Back'), ('BOTTOM', u'\u21fd')])],
      'KEY_RETURN': [
          fix_svg_key_closure(self.svg_name('two-line-wide'),
          [('TOP', 'Enter'), ('BOTTOM', u'\u23CE')])],
      'KEY_CAPS_LOCK': [
          fix_svg_key_closure(self.svg_name('two-line-wide'),
          [('TOP', 'Capslock'), ('BOTTOM', '')])],
      'KEY_MULTI_KEY': [
          fix_svg_key_closure(self.svg_name('two-line-wide'),
          [('TOP', 'Compose'), ('BOTTOM', '')])],
    })
    return ftn

  def create_window(self):
    """Create the main window."""
    self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    self.window.set_resizable(False)

    self.window.set_title('Keyboard Status Monitor')
    width, height = 30, 48
    self.window.set_default_size(int(width), int(height))
    self.window.set_decorated(True)

    self.mouse_indicator_win = shaped_window.ShapedWindow(
        self.svg_name('mouse-indicator'),
        timeout=self.options.visible_click_timeout)

    self.mouse_follower_win = shaped_window.ShapedWindow(
        self.svg_name('mouse-follower'))
    if self.options.follow_mouse:
        self.mouse_follower_win.show()

    self.window.set_opacity(self.options.opacity)
    self.window.set_keep_above(True)

    self.event_box = gtk.EventBox()
    self.window.add(self.event_box)
    self.event_box.show()

    self.hbox = gtk.HBox(False, 0)
    self.event_box.add(self.hbox)

    self.layout_boxes()
    self.hbox.show()

    self.add_events()

    self.set_accept_focus(False)
    self.window.set_skip_taskbar_hint(True)

    old_x = self.options.x_pos
    old_y = self.options.y_pos
    if old_x != -1 and old_y != -1 and old_x and old_y:
      self.window.move(old_x, old_y)
    self.window.show()

  def layout_boxes(self):
    for child in self.hbox.get_children():
      self.hbox.remove(child)

  def svg_name(self, fname):
    """Return an svg filename given the theme, system."""
    themepath = self.options.themes[self.options.theme][1]
    fullname = os.path.join(themepath, '%s%s.svg' % (fname, self.svg_size))
    if self.svg_size and not os.path.exists(fullname):
      # Small not found, defaulting to large size
      fullname = os.path.join(themepath, '%s.svg' % fname)
    return fullname

  def add_events(self):
    """Add events for the window to listen to."""
    self.window.connect('destroy', self.destroy)
    self.window.connect('button-press-event', self.button_pressed)
    self.window.connect('button-release-event', self.button_released)
    self.window.connect('leave-notify-event', self.pointer_leave)
    self.event_box.connect('button_release_event', self.right_click_handler)

    accelgroup = gtk.AccelGroup()
    key, modifier = gtk.accelerator_parse('<Control>q')
    accelgroup.connect_group(key, modifier, gtk.ACCEL_VISIBLE, self.quit_program)

    key, modifier = gtk.accelerator_parse('<Control>s')
    accelgroup.connect_group(key, modifier, gtk.ACCEL_VISIBLE, self.show_settings_dlg)
    self.window.add_accel_group(accelgroup)

    gobject.idle_add(self.on_idle)

  def button_released(self, unused_widget, evt):
    """A mouse button was released."""
    if evt.button == 1:
      self.move_dragged = None
    return True

  def button_pressed(self, widget, evt):
    """A mouse button was pressed."""
    self.set_accept_focus(True)
    if evt.button == 1:
      self.move_dragged = widget.get_pointer()
      self.window.set_opacity(self.options.opacity)
      # remove no_press_timer
      if self.no_press_timer:
        gobject.source_remove(self.no_press_timer)
        self.no_press_timer = None
    return True

  def pointer_leave(self, unused_widget, unused_evt):

    self.set_accept_focus(False)

  def set_accept_focus(self, accept_focus=True):

    self.window.set_accept_focus(accept_focus)
    if accept_focus:
      logging.debug('window now accepts focus')
    else:
      logging.debug('window now does not accept focus')

  def _window_moved(self):
    """The window has moved position, save it."""
    if not self.move_dragged:
      return
    old_p = self.move_dragged
    new_p = self.window.get_pointer()
    x, y = self.window.get_position()
    x, y = x + new_p[0] - old_p[0], y + new_p[1] - old_p[1]
    self.window.move(x, y)

    logging.info('Moved window to %d, %d' % (x, y))
    self.options.x_pos = x
    self.options.y_pos = y

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

  def reset_no_press_timer(self):
    """Initialize no_press_timer"""
    if not self.options.no_press_fadeout:
      return
    logging.debug('Resetting no_press_timer')
    if not self.window.get_property('visible'):
      self.window.move(self.options.x_pos, self.options.y_pos)
      self.window.show()
    self.window.set_opacity(self.options.opacity)
    if self.no_press_timer:
      gobject.source_remove(self.no_press_timer)
      self.no_press_timer = None
    self.no_press_timer = gobject.timeout_add(int(self.options.no_press_fadeout * 1000), self.no_press_fadeout)

  def no_press_fadeout(self, begin=True):
    """Fadeout the window in a second
    Args:
      begin: indicate if this timeout is requested by handle_event.
    """
    opacity = self.window.get_opacity() - self.options.opacity / 10.0
    if opacity < 0.0:
      opacity = 0.0;
    logging.debug('Set opacity = %f' % opacity)
    self.window.set_opacity(opacity)
    if opacity == 0.0:
      self.window.hide()
      # No need to fade out more
      self.no_press_timer = None
      return False

    if begin:
      # Recreate a new timer with 0.1 seccond interval
      self.no_press_timer = gobject.timeout_add(100, self.no_press_fadeout)
      # The current self.options.no_press_fadeout interval will not be timed
      # out again.
      return False

  def _show_down_key(self, name):
    """Show the down key.
    Normally True, unless combo is set.
    Args:
      name: name of the key being held down.
    Returns:
      True if the key should be shown
    """
    if not self.options.only_combo:
      return True
    if self.is_shift_code(name):
      return True
    return False

  def is_shift_code(self, code):
    if code in ('SHIFT', 'ALT', 'ALTGR', 'CTRL', 'META'):
      return True
    return False

  def handle_key(self, scan_code, xlib_name, value):
    """Handle a keyboard event."""
    code, medium_name, short_name = self.modmap.get_and_check(scan_code,
                                                              xlib_name)
    if not code:
      logging.info('No mapping for scan_code %s', scan_code)
      return
    logging.debug('Scan code %s, Key %s pressed = %r', scan_code,
                                                       code, medium_name)
    if code in self.name_fnames:
      return
    if code.startswith('KEY_KP'):
      letter = medium_name
      if code not in self.name_fnames:
        template = 'one-char-numpad-template'
        self.name_fnames[code] = [
            fix_svg_key_closure(self.svg_name(template), [('&amp;', letter)])]
      return

    if code.startswith('KEY_'):
      letter = medium_name
      if code not in self.name_fnames:
        logging.debug('code not in %s', code)
        if len(letter) == 1:
          template = 'one-char-template'
        else:
          template = 'multi-char-template'
        self.name_fnames[code] = [
            fix_svg_key_closure(self.svg_name(template), [('&amp;', letter)])]
      else:
        logging.debug('code in %s', code)
      return

  def quit_program(self, *unused_args):
    """Quit the program."""
    self.devices.stop_listening()
    self.destroy(None)

  def destroy(self, unused_widget, unused_data=None):
    """Also quit the program."""
    self.devices.stop_listening()
    self.options.save()
    gtk.main_quit()

  def right_click_handler(self, unused_widget, event):
    """Handle the right click button and show a menu."""
    if event.button != 3:
      return

    menu = self.create_context_menu()

    menu.show()
    menu.popup(None, None, None, event.button, event.time)

  def create_context_menu(self):
    """Create a context menu on right click."""
    menu = gtk.Menu()

    settings_click = gtk.MenuItem(_('_Settings...\tCtrl-S'))
    settings_click.connect_object('activate', self.show_settings_dlg, None)
    settings_click.show()
    menu.append(settings_click)

    quitcmd = gtk.MenuItem(_('_Quit\tCtrl-Q'))
    quitcmd.connect_object('activate', self.destroy, None)
    quitcmd.show()

    menu.append(quitcmd)
    return menu

  def show_settings_dlg(self, *unused_args):
    """Show the settings dialog."""
    dlg = settings.SettingsDialog(self.window, self.options)
    dlg.connect('settings-changed', self.settings_changed)
    dlg.show_all()
    dlg.run()
    dlg.destroy()

  def settings_changed(self, unused_dlg):
    """Event received from the settings dialog."""
    self.layout_boxes()
    self.mouse_indicator_win.hide()
    self.mouse_indicator_win.timeout = self.options.visible_click_timeout
    self.window.set_decorated(self.options.decorated)
    self.name_fnames = self.create_names_to_fnames()
    self.pixbufs.reset_all(self.name_fnames, 1.0)

    # all this to get it to resize smaller
    x, y = self.window.get_position()
    self.hbox.resize_children()
    self.window.resize_children()
    self.window.reshow_with_initial_size()
    self.hbox.resize_children()
    self.event_box.resize_children()
    self.window.resize_children()
    self.window.move(x, y)

    # reload keymap
    self.modmap = mod_mapper.safely_read_mod_map(
            self.options.kbd_file, self.options.kbd_files)

def create_options():
  opts = options.Options()

  opts.add_option(opt_long='--visible-click-timeout', dest='visible_click_timeout',
                  type='float', default=0.2,
                  ini_group='ui', ini_name='visible_click_timeout',
                  help=_('Timeout before highly visible click disappears. '
                         'Defaults to %default'))
  opts.add_option(opt_long='--no-press-fadeout', dest='no_press_fadeout',
                  type='float', default=0.0,
                  ini_group='ui', ini_name='no_press_fadeout',
                  help=_('Fadeout the window after a period with no key press. '
                         'Defaults to %default seconds (Experimental)'))
  opts.add_option(opt_long='--only_combo', dest='only_combo', type='bool',
                  ini_group='ui', ini_name='only_combo',
                  default=False,
                  help=_('Show only key combos (ex. Control-A)'))
  opts.add_option(opt_long='--sticky', dest='sticky_mode', type='bool',
                  ini_group='ui', ini_name='sticky_mode',
                  default=False,
                  help=_('Sticky mode'))
  opts.add_option(opt_long='--visible_click', dest='visible_click', type='bool',
                  ini_group='ui', ini_name='visible-click',
                  default=False,
                  help=_('Show where you clicked'))
  opts.add_option(opt_long='--follow_mouse', dest='follow_mouse', type='bool',
                  ini_group='ui', ini_name='follow-mouse',
                  default=False,
                  help=_('Show the mouse more visibly'))
  opts.add_option(opt_long='--kbdfile', dest='kbd_file',
                  ini_group='devices', ini_name='map',
                  default=None,
                  help=_('Use this kbd filename.'))
  opts.add_option(opt_short='-t', opt_long='--theme', dest='theme', type='str',
                  ini_group='ui', ini_name='theme', default='classic',
                  help=_('The theme to use when drawing status images (ex. "-t apple").'))
  opts.add_option(opt_long='--reset', dest='reset', type='bool',
                  help=_('Reset all options to their defaults.'),
                  default=None)

  opts.add_option(opt_short=None, opt_long='--opacity', type='float',
                  dest='opacity', default=1.0, help='Opacity of window',
                  ini_group='ui', ini_name='opacity')
  opts.add_option(opt_short=None, opt_long=None, type='int',
                  dest='x_pos', default=-1, help='Last X Position',
                  ini_group='position', ini_name='x')
  opts.add_option(opt_short=None, opt_long=None, type='int',
                  dest='y_pos', default=-1, help='Last Y Position',
                  ini_group='position', ini_name='y')

  opts.add_option_group(_('Developer Options'), _('These options are for developers.'))
  opts.add_option(opt_long='--loglevel', dest='loglevel', type='str', default='',
                  help=_('Logging level'))
  opts.add_option(opt_short='-d', opt_long='--debug', dest='debug', type='bool',
                  default=False,
                  help=_('Output debugging information. '
                         'Shorthand for --loglevel=debug'))
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
  opts.read_ini_file(os.path.join(settings.get_config_dir(), 'config'))
  desc = _('Usage: %prog [Options...]')
  opts.parse_args(desc, sys.argv)

  opts.themes = settings.get_themes()
  if opts.theme and opts.theme not in opts.themes:
    print _('Theme %r does not exist') % opts.theme
    print
    print _('Please make sure %r can be found in '
            'one of the following directories:') % opts.theme
    print
    for theme_dir in settings.get_config_dirs('themes'):
      print ' - %s' % theme_dir
    sys.exit(-1)
  if opts.reset:
    print _('Resetting to defaults.')
    opts.reset_to_defaults()
    opts.save()
  keymon = KeyMon(opts)
  try:
    gtk.main()
  except KeyboardInterrupt:
    keymon.quit_program()

if __name__ == '__main__':
  #import cProfile
  #cProfile.run('main()', 'keymonprof')
  main()
