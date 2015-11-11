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
"""IDLE like Console for Gedit, hit F5 and it executes the module"""

from gi.repository import GObject, Gedit, Gio
from betterpythonconsole import consolefunctions


class BetterConsoleAppActivatable(GObject.Object, Gedit.AppActivatable):

    app = GObject.property(type=Gedit.App)

    def do_activate(self):
        #   action        self.on_clear_document_activate)])
        self.app.add_accelerator("F5", "win.betterconsole", None)
        self.menu_ext = self.extend_menu("tools-section")
        item = Gio.MenuItem.new(_("Better Console"), "win.betterconsole")
        self.menu_ext.append_menu_item(item)

    def do_deactivate(self):
        """Pull our item from the menu."""
        self.app.remove_accelerator("win.betterconsole", None)
        self.menu_ext = None


class BetterConsoleWindowActivatable(GObject.Object, Gedit.WindowActivatable):
    """This Class creates the Gedit plugin. """

    window = GObject.property(type=Gedit.Window)

    def __init__(self):
        GObject.Object.__init__(self)
        self._instances = {}

    def do_activate(self):
        """This adds the plugin to the running Gedit. This method is used
        when the plugin is turned on and then when Gedit starts"""
        home_path = __path__[0]
        self._instances[self.window] = consolefunctions.BetterConsoleHelper(
            self, self.window, home_path
        )

        action = Gio.SimpleAction(name="betterconsole")
        action.connect('activate', self.on_clear_document_activate)
        self.window.add_action(action)

        for view in self.window.get_views():
            self.add_helper(view, self.window)

    def do_deactivate(self):
        """This removes the plugin from the running Gedit."""
        self._instances[self.window].deactivate()
        del self._instances[self.window]

    def update_ui(self):
        """We do not use this yet."""
        self._instances[self.window].update_ui()

    def on_clear_document_activate(self, action, data=None):
        self._instances[self.window].on_clear_document_activate(action)

