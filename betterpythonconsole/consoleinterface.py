#!/usr/bin/env python

#    This file is part of the Better Python Console Plugin for Gedit
#    Copyright (C) 2007 Zeth Green <zethgreen@gmail.com>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# ------------------------------------------------------------------------------
#
#    Executing this file in Gedit through the Better Python Console Plugin
#    is not recommended as it will cause a hairy loop and make your X server
#    unresponsive. You have been warned!
#
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
#    This module is based on pycons.py by Nicolas Rougier,
#    which in turn is based on the Gimp's GTK Interactive Console.
#    To find out more please visit http://www.loria.fr/~rougier/
#
#    Original Copyright (c) 1998 James Henstridge, 2006 Nicolas Rougier
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
# ------------------------------------------------------------------------------


""" Interactive GTK console

This console is heavily based on the GTK Interactive Console bundled with
The Gimp and implements an interactive python session in a GTK window.

"""

__version__ = '1.0'
__author__ = 'Nicolas Rougier'
__email__ = 'Nicolas.Rougier@loria.fr'


import os.path
import sys
import traceback

from gi.repository import Gtk, GConf, Pango, GObject, Gdk

stdout = sys.stdout
if not hasattr(sys, 'ps1'):
    sys.ps1 = '>>> '
if not hasattr(sys, 'ps2'):
    sys.ps2 = '... '


# =============================================================================
class gtkoutfile:
    """
    A fake output file object.  It sends output to a GTK TextView widget,
    and if asked for a file number, returns one set on instance creation
    """

    def __init__(self, console, fn, font):
        self.fn = fn
        self.console = console
        # self.__b = w.get_buffer()
        # self.__ins = self.__b.get_mark('insert')
        self.font = font

    def close(self):
        pass

    flush = close

    def fileno(self):
        return self.fn

    def isatty(self):
        return False

    def read(self, a):
        return ''

    def readline(self):
        return ''

    def readlines(self):
        return []

    def write(self, s):
        self.console.write(s, self.font)

    def writelines(self, l):
        for s in l:
            self.console.write(s, self.font)

    def seek(self, a):
        raise IOError(29, 'Illegal seek')

    def tell(self):
        raise IOError(29, 'Illegal seek')

    truncate = tell


# =============================================================================
class gtkinfile:
    """
    A fake input file object.  It receives input from a GTK TextView widget,
    and if asked for a file number, returns one set on instance creation
    """

    def __init__(self, console, fn):
        self.fn = fn
        self.console = console

    def close(self):
        pass

    flush = close

    def fileno(self):
        return self.fn

    def isatty(self):
        return False

    def read(self, a):
        return self.readline()

    def readline(self):
        self.console.input_mode = True
        while self.console.input_mode:
            while Gtk.events_pending():
                Gtk.main_iteration()
        s = self.console.input
        self.console.input = ''
        return s + '\n'

    def readlines(self):
        return []

    def write(self, s):
        return None

    def writelines(self, l):
        return None

    def seek(self, a):
        raise IOError(29, 'Illegal seek')

    def tell(self):
        raise IOError(29, 'Illegal seek')

    truncate = tell


# =============================================================================
class History:
    """ Basic command history class
    """

    def __init__(self):
        """ Initializes history """

        self.history = ['']
        self.position = len(self.history) - 1

    def prev(self, current):
        """ Get previous command in history """

        if self.position > 0:
            l = current
            if len(l) > 0 and l[0] == '\n':
                l = l[1:]
            if len(l) > 0 and l[-1] == '\n':
                l = l[:-1]
            if self.position > 0:
                if self.position == (len(self.history)-1):
                    self.history[len(self.history)-1] = l
                self.position = self.position - 1
                return self.history[self.position]
        return current

    def next(self, current):
        """ Get next command in history """

        if self.position < len(self.history) - 1:
            self.position = self.position + 1
            return self.history[self.position]
        return current

    def append(self, line):
        """ Append a new command to history """

        self.position = len(self.history) - 1
        if not len(line):
            return
        if (self.position == 0) or (
            self.position > 0 and line != self.history[self.position-1]
        ):
            self.history[self.position] = line
            self.position = self.position + 1
            self.history.append('')

    def open(self, filename):
        """ Open an history file """

        file = open(filename)
        self.history = []
        for l in file:
            self.history.append(l[:-1])
        self.history.append('')
        self.position = len(self.history)-1
        file.close()

    def save(self, filename):
        """ Save history to a file """

        file = open(filename, 'w')
        for l in self.history:
            if len(l) > 0:
                file.write(l+'\n')
        file.close()

    def __repr__(self):
        """ History representation """

        return self.history.__repr__()


# =============================================================================
class Console(Gtk.ScrolledWindow):
    """ Interactive GTK console class """

    def __init__(self, namespace={}, quit_handler=None):
        """ Initialize console
        """
        # Get font from gedit's entries in gconf
        client = GConf.Client.get_default()
        default_question = client.get_bool(
            '/apps/gedit-2/preferences/editor/font/use_default_font')
        if default_question:
            userfont = client.get_string(
                '/desktop/gnome/interface/font_name')
        else:
            userfont = client.get_string(
                '/apps/gedit-2/preferences/editor/font/editor_font')

        # Setup scrolled window
        GObject.GObject.__init__(self)
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self.set_border_width(0)

        # Setup text view
        self.text = Gtk.TextView()
        self.text.set_property('can-focus', True)
        self.text.modify_font(Pango.FontDescription(userfont))
        self.text.set_editable(True)
        self.text.set_wrap_mode(True)
        self.text.set_left_margin(1)
        self.text.set_right_margin(1)
        self.text.set_size_request(0, 0)

        # Setup text buffer
        self.buffer = self.text.get_buffer()
        self.buffer.create_tag('prompt', weight=Pango.Weight.BOLD)
        self.buffer.create_tag(
            'script', foreground='darkgrey', style=Pango.Style.OBLIQUE)
        self.buffer.create_tag('normal', foreground='blue')
        self.buffer.create_tag(
            'error', foreground='red', style=Pango.Style.OBLIQUE)
        self.buffer.create_tag('extern', foreground='orange')
        self.buffer.create_tag(
            'center', justification=Gtk.Justification.CENTER)

        # Setup event handlers
        self.text.add_events(Gdk.EventMask.KEY_PRESS_MASK)
        self.text.connect('button-press-event', self.on_button_press)
        self.text.connect('key-press-event', self.on_key_pressed)
        self.text.connect('drag-data-received', self.on_drag_data_received)
        self.add(self.text)

        # Internal setup
        self.namespace = namespace
        self.cmd = ''
        self.input = ''
        self.input_mode = False
        self.linestart = 0
        self.quit_handler = self.quit
        if quit_handler:
            self.quit_handler = quit_handler

        # Setup hooks for standard output.
        self.stdout = gtkoutfile(self, sys.stdout.fileno(), 'normal')
        self.stderr = gtkoutfile(self, sys.stderr.fileno(), 'error')
        self.stdin = gtkinfile(self, sys.stdin.fileno())

        # Setup command history
        self.history = History()
        self.namespace['__history__'] = self.history
        self.show_all()

    def banner(self):
        """ Display python banner """

#        iter = self.buffer.get_iter_at_mark(self.buffer.get_insert())
#        self.buffer.insert (iter, 'Python %s\n' % sys.version)
#        iter = self.buffer.get_iter_at_mark(self.buffer.get_insert())
#        self.buffer.insert (iter, '''Type "help", "copyright", "credits" or'''
#                                  ''' "license" for more information.\n''')
        self.text.scroll_to_mark(self.buffer.get_insert(), 0, False, 0, 0)
        self.prompt1()

    def prompt1(self):
        """ Display normal prompt """

        self.prompt = sys.ps1
        self.write(self.prompt, 'prompt')

    def prompt2(self):
        """ Display continuation prompt """

        self.prompt = sys.ps2
        self.write(self.prompt, 'prompt')

    def clear(self):
        """ Clear text buffer & view """

        line = self.current_line()
        self.buffer.delete(
            self.buffer.get_start_iter(), self.buffer.get_end_iter())
        self.write(self.prompt, 'prompt')
        self.write(line)

    def write(self, line, style=None):
        """ Write a line using given style (if any) """

        start, end = self.text.get_buffer().get_bounds()
        if style is None:
            self.text.get_buffer().insert(end, line)
        else:
            self.text.get_buffer().insert_with_tags_by_name(end, line, style)
        self.text.scroll_mark_onscreen(self.buffer.get_insert())
        self.linestart = self.buffer.get_end_iter().get_offset()

    def replace(self, line):
        """ Replace current active line with line """

        start, end = self.current_line_bounds()
        self.text.get_buffer().delete(start, end)
        l = self.linestart
        self.write(line)
        self.linestart = l

    def current_line(self):
        """ Get current active line """

        start, end = self.current_line_bounds()
        return self.buffer.get_text(start, end, True)

    def current_line_bounds(self):
        """ Get current active line bounds """

        l = self.buffer.get_line_count() - 1
        start = self.buffer.get_iter_at_line(l)
        # mark = self.buffer.get_mark('linestart')
        # start = self.buffer.get_iter_at_mark (mark)
        if start.get_chars_in_line() >= 4:
            start.forward_chars(4)
        end = self.buffer.get_end_iter()
        return start, end

    def is_balanced(self, line):
        """ Checks line balance for brace, bracket, parenthese and string quote

        This helper function checks for the balance of brace, bracket,
        parenthese and string quote. Any unbalanced line means to wait until
        some other lines are fed to the console.
        """

        s = line
        s = filter(lambda x: x in '()[]{}"\'', s)
        s = s.replace("'''", "'")
        s = s.replace('"""', '"')
        instring = False
        brackets = {'(': ')', '[': ']', '{': '}', '"': '"', '\'': '\''}
        stack = []

        while len(s):
            if not instring:
                if s[0] in ')]}':
                    if stack and brackets[stack[-1]] == s[0]:
                        del stack[-1]
                    else:
                        return False
                elif s[0] in '"\'':
                    if stack and brackets[stack[-1]] == s[0]:
                        del stack[-1]
                        instring = False
                    else:
                        stack.append(s[0])
                        instring = True
                else:
                    stack.append(s[0])
            else:
                if s[0] in '"\'' and stack and brackets[stack[-1]] == s[0]:
                    del stack[-1]
                    instring = False
            s = s[1:]
        return len(stack) == 0

    def eval(self):
        """ Evaluate if current line is ready for execution """

        l = self.current_line()
        self.write('\n')
        self.history.append(l)
        end = self.buffer.get_end_iter()
        self.buffer.place_cursor(end)

        if l == '':
            cmd = self.cmd
            self.cmd = ''
            self.execute(cmd)
            self.prompt1()
            return

        self.cmd = self.cmd + l + '\n'
        if not self.is_balanced(self.cmd):
            self.prompt2()
            return
        l = l.rstrip()
        if len(l) > 0:
            if l[-1] == ':' or l[-1] == '\\' or l[0] in ' \11':
                self.prompt2()
                return

        cmd = self.cmd
        self.cmd = ''
        self.execute(cmd)
        self.prompt1()
        return

    def idle(self, frame, event, arg):
        """ Idle function to be used when running a command.

        This idle function is set as a trace function when executing some
        commands, it allows to process gtk events even when executing code.
        """

        while Gtk.events_pending():
            Gtk.main_iteration()
        return self.idle

    def execute(self, cmd):
        """ Execute a given command """

        sys.stdout, self.stdout = self.stdout, sys.stdout
        sys.stderr, self.stderr = self.stderr, sys.stderr
        sys.stdin,  self.stdin = self.stdin,  sys.stdin
        sys.settrace(self.idle)

        try:
            try:
                r = eval(cmd, self.namespace, self.namespace)

                if r is not None:
                    print(r)
            except SyntaxError:
                exec(cmd, self.namespace)
        except:
            if hasattr(sys, 'last_type') and sys.last_type == SystemExit:
                self.quit_handler()
            else:
                try:
                    info = sys.exc_info()
                    tb = info[2]
                    if tb:
                        tb = tb.tb_next
                    traceback.print_exception(info[0], info[1], tb)
                except:
                    sys.stderr, self.stderr = self.stderr, sys.stderr
                    traceback.print_exc()
        sys.settrace(None)
        sys.stdout, self.stdout = self.stdout, sys.stdout
        sys.stderr, self.stderr = self.stderr, sys.stderr
        sys.stdin,  self.stdin = self.stdin,  sys.stdin

    def open(self, filename):
        """ Open and execute a given filename """

        if not filename:
            return
        if not os.path.exists(filename):
            dialog = Gtk.MessageDialog(
                None, Gtk.DialogFlags.DESTROY_WITH_PARENT,
                Gtk.MessageType.ERROR, Gtk.ButtonsType.OK,
                "Unable to open '%s', the file does not exist." % filename)
            dialog.run()
            dialog.destroy()
            return

        # By here we need to have the Path sorted out
        # or we will be north of the river.
        # Does not matter if it has been called without a file.
        sys.path.append(os.path.dirname(filename))

        f = open(filename)
        try:
            self.write("Executing '%s'\n\n" % filename, 'extern')
#            for line in f:
#                self.write ('\t'+line, 'script')
            self.write('\n')
            self.execute("exec(open('%s').read())" % filename)
            self.prompt1()
        finally:
            f.close()

    def quit(self, *args):
        """ Default handler on quit """
        Gtk.main_quit()
        return True

    def on_drag_data_received(
        self, widget, context, x, y, selection, info, etime
    ):
        """ Handler for drag data """

        self.write(selection.data)
        widget.emit_stop_by_name("drag-data-received")
        self.text.grab_focus()

    def on_button_press(self, *args):
        """ Grab focus when window is clicked """

        self.text.grab_focus()
        return True

    def on_key_pressed(self, widget, event):
        """ Key pressed handler """

        # Enter
        if event.keyval == Gdk.KEY_Return:
            if self.input_mode:
                self.input_mode = False
                end = self.buffer.get_end_iter()
                start = self.buffer.get_iter_at_offset(self.linestart)
                self.input = self.buffer.get_text(start, end, True)
                self.write('\n')
            else:
                self.eval()
            return True

        # Previous command
        elif event.keyval in (Gdk.KEY_KP_Up, Gdk.KEY_Up):
            if not self.input_mode:
                self.replace(self.history.prev(self.current_line()))
            return True

        # Next command
        elif event.keyval in (Gdk.KEY_KP_Down, Gdk.KEY_Down):
            if not self.input_mode:
                self.replace(self.history.next(self.current_line()))
            return True

        # Left arrow (control cursor position relative to prompt)
        elif event.keyval in (Gdk.KEY_KP_Left, Gdk.KEY_Left):
            iter = self.buffer.get_iter_at_mark(self.buffer.get_insert())
            return iter.get_offset() == self.linestart

        # Backspace
        elif event.keyval == Gdk.KEY_BackSpace:
            iter = self.buffer.get_iter_at_mark(self.buffer.get_insert())
            return iter.get_offset() == self.linestart

        # Home
        elif event.keyval == Gdk.KEY_Home:
            start = self.buffer.get_iter_at_offset(self.linestart)
            self.text.get_buffer().place_cursor(start)
            return True

        elif event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            # Ctrl-A
            if event.keyval in (Gdk.KEY_A, Gdk.KEY_a):
                start = self.buffer.get_iter_at_offset(self.linestart)
                self.text.get_buffer().place_cursor(start)
                return True

            # Ctrl-E
            elif event.keyval in (Gdk.KEY_E, Gdk.KEY_e):
                if self.input_mode:
                    return True
                end = self.buffer.get_end_iter()
                self.buffer.place_cursor(end)
                return True

            # Ctrl-D
            elif event.keyval in (Gdk.KEY_D, Gdk.KEY_d):
                if self.input_mode:
                    return True
                iter = self.buffer.get_iter_at_mark(self.buffer.get_insert())
                if iter.get_line_offset() == 4:
                    self.quit_handler()
                return True

            # Ctrl-L
            elif event.keyval in (Gdk.KEY_L, Gdk.KEY_l):
                if not self.input_mode:
                    self.clear()
                return True
        return False


# =============================================================================
class ConsoleWindow:
    """ Interactive GTK console window """

    def __init__(self, ns, title='Python', command=None):
        """ Initialize s console window """

        self.win = Gtk.Window()
        self.win.set_default_size(640, 400)
        self.win.set_border_width(3)
        self.win.connect("destroy", lambda w: Gtk.main_quit())
        self.win.connect("delete_event", lambda w, e: Gtk.main_quit())
        self.win.set_title(title)
        self.console = Console(namespace=ns)
        self.win.add(self.console)
        self.console.banner()
        if command:
            self.console.execute(command)
        self.win.show_all()

        return


if __name__ == '__main__':
    conswin = ConsoleWindow(
        {
            '__builtins__': __builtins__,
            '__name__': '__main__',
            '__doc__': None
        },
        title='Python Console'
    )
    if len(sys.argv) > 1:
        conswin.console.open(sys.argv[1])
    Gtk.main()

