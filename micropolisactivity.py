import os

import time
import signal
import subprocess
import thread
import fcntl
import platform

from gettext import gettext as _

from gi.repository import Gtk

from sugar3 import profile
from sugar3.activity import activity
from sugar3.activity.activity import get_bundle_path
from sugar3.activity.widgets import StopButton
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.presence import presenceservice
from sugar3.graphics.toolbarbox import ToolbarBox

WITH_PYGAME = True

try:
    import pygame.mixer
    pygame.mixer.init()

except:
    WITH_PYGAME = False

ARCH = "x86-64"
if platform.machine().startswith('arm'):
    ARCH = "arm"
else:
    if platform.architecture()[0] == '64bit':
        ARCH = "x86-64"
    else:
        ARCH = "x86"


def QuoteTCL(s):
    return s.replace('"', '\\"')


class MicroPolisActivity(activity.Activity):

    def __init__(self, handle):

        activity.Activity.__init__(self, handle)

        self._handle = handle
        self.closed_from_game = False

        self.set_title(_('MicroPolis Activity'))
        self.connect('destroy', self._destroy_cb)
        #self.connect('focus-in-event', self._focus_in_cb)
        #self.connect('focus-out-event', self._focus_out_cb)

        self._bundle_path = get_bundle_path()

        self.setup_toolbar()
        self.load_libs_dirs()

        self.socket = Gtk.Socket()
        self.socket.connect("realize", self._start_all_cb)
        self.set_canvas(self.socket)

        self.show_all()

    def setup_toolbar(self):
        toolbarbox = ToolbarBox()
        self.set_toolbar_box(toolbarbox)

        toolbarbox.toolbar.insert(ActivityToolbarButton(self), -1)

        separator = Gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        toolbarbox.toolbar.insert(separator, -1)

        toolbarbox.toolbar.insert(StopButton(self), -1)

    def load_libs_dirs(self):
        os.environ["SINHOME"] = self._bundle_path
        os.environ['LD_LIBRARY_PATH'] = os.path.join(self._bundle_path, "libs/", ARCH)

    def _start_all_cb(self, widget):
        win = str(self.socket.get_id())

        if (win.endswith("L")):  # L of "Long"
            win = win[:-1]
        
        # Run game
        command = os.path.join(self._bundle_path, "res/sim.%s" % ARCH)

        args = [
            command,
            #'-R', win, # Set root window to socket window id
            '-t',      # Interactive tty mode, so we can send it commands.
        ]

        self._process = subprocess.Popen(args,
                                         stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE,
                                         close_fds=True,
                                         cwd=self._bundle_path,
                                         preexec_fn=lambda: os.chdir(self._bundle_path))

        self._stdout_thread = thread.start_new(self._stdout_thread_function, ())

        uri = self._handle.uri or ''
        self.send_process('SugarStartUp "' + QuoteTCL(uri) + '"\n')

        nick = profile.get_nick_name() or ''
        self.send_process('SugarNickName "' + QuoteTCL(nick) + '"\n')

    def _stdout_thread_function(self, *args, **keys):
        f = self._process.stdout
        fcntl.fcntl(f.fileno(), fcntl.F_SETFD, 0)

        while True:
            line = 'XXX'
            try:
                line = f.readline()

            except Exception, e:
                break

            line = line.strip()
            if not line:
                continue

            words = line.strip().split(' ')
            command = words[0]
            if command == 'PlaySound':
                self.play_sound(words[1])

            elif command == 'QuitMicropolis':
                self.close(True)

    def play_sound(self, name):
        fileName = os.path.join(self._bundle_path, 'res/sounds', name.lower() + '.wav')

        if WITH_PYGAME:
            sound = pygame.mixer.Sound(fileName)
            sound.play()

        else:
            print "Can't play sound: " + fileName + " " + str(e)

    def send_process(self, message):
        self._process.stdin.write(message)

    def share(self):
        Activity.share(self)
        self.send_process('SugarShare\n')

    def _destroy_cb(self, window):
        try:
            os.kill(self._process.pid, signal.SIGUSR1)
        except:
            pass

    def _focus_in_cb(self, window, event):
        self.send_process('SugarActivate\n')

    def _focus_out_cb(self, window, event):
        self.send_process('SugarDeactivate\n')

