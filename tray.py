"""Native Windows tray, sharing pywebview's existing WinForms runtime."""
import logging
import threading


def finish_shutdown(stop, worker, destroy, timeout=8):
    stop.set()
    if worker.ident:
        worker.join(timeout=timeout)
    destroy()


class WindowsTray:
    def __init__(self, window, stop, worker, icon_path):
        self.window, self.stop, self.worker = window, stop, worker
        self.icon_path = str(icon_path)
        self.exiting = threading.Event()
        self.install_lock = threading.Lock()
        self.installed = False
        self.icon = None

    def install(self):
        with self.install_lock:
            if self.installed:
                return
            self.installed = True
        from System import Action
        self.window.native.BeginInvoke(Action(self._install_gui))

    def _install_gui(self):
        from System.Drawing import Icon
        from System.Windows.Forms import ContextMenuStrip, NotifyIcon
        try:
            self.form = self.window.native
            self.image = Icon(self.icon_path)
            self.menu = ContextMenuStrip()
            self.open_item = self.menu.Items.Add('Open')
            self.close_item = self.menu.Items.Add('Close')
            self.open_item.Click += self._open
            self.close_item.Click += self._close
            self.icon = NotifyIcon()
            self.icon.Icon = self.image
            self.icon.Text = 'SoundCloud RPC'
            self.icon.ContextMenuStrip = self.menu
            self.icon.DoubleClick += self._open
            self.icon.Visible = True
            self.form.FormClosing += self._on_closing
            self.form.FormClosed += self._on_closed
        except Exception:
            logging.getLogger(__name__).exception('Unable to create tray icon')
            self._on_closed()

    def _open(self, *_):
        if self.exiting.is_set():
            return
        from System.Windows.Forms import FormWindowState
        self.form.Show()
        if self.form.WindowState == FormWindowState.Minimized:
            self.form.WindowState = FormWindowState.Normal
        self.form.Activate()

    def _on_closing(self, sender, args):
        if not self.exiting.is_set() and self.icon and self.icon.Visible:
            args.Cancel = True
            self.form.Hide()

    def _close(self, *_):
        if self.exiting.is_set():
            return
        self.exiting.set()
        self.close_item.Enabled = False
        # The UI remains responsive while the RPC worker clears its activity.
        threading.Thread(target=self._finish, name='tray-shutdown', daemon=True).start()

    def _finish(self):
        from System import Action
        finish_shutdown(self.stop, self.worker,
            lambda: self.form.BeginInvoke(Action(self.form.Close)))

    def _on_closed(self, *_):
        self.exiting.set()
        if self.icon is not None:
            self.icon.Visible = False
            self.icon.Dispose()
            self.icon = None
        if hasattr(self, 'menu'):
            self.menu.Dispose()
        if hasattr(self, 'image'):
            self.image.Dispose()
