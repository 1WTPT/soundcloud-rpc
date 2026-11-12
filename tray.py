"""Independent STA message loop keeps the tray usable when the browser hangs."""
import logging
import os
import threading


def finish_shutdown(stop, worker, destroy, timeout=1.5):
    stop.set()
    if worker.ident:
        worker.join(timeout=timeout)
    destroy()


class WindowsTray:
    def __init__(self, window, stop, worker, icon_path, force_exit=os._exit):
        self.window, self.stop, self.worker = window, stop, worker
        self.icon_path = str(icon_path)
        self.force_exit = force_exit
        self.exiting = threading.Event()
        self.install_lock = threading.Lock()
        self.installed = False
        self.icon = None
        self.restart_requested = False

    def install(self):
        with self.install_lock:
            if self.installed:
                return
            self.installed = True
        from System import Action
        from System.Threading import Thread, ThreadStart, ApartmentState
        self.form = self.window.native
        self.native_thread = Thread(ThreadStart(self._run_tray))
        self.native_thread.SetApartmentState(ApartmentState.STA)
        self.native_thread.IsBackground = True
        self.native_thread.Start()
        self.form.BeginInvoke(Action(self._install_toolbar))

    def _run_tray(self):
        from System.Drawing import Icon
        from System.Windows.Forms import Application, ApplicationContext, ContextMenuStrip, NotifyIcon, Control
        self.context = ApplicationContext()
        self.dispatcher = Control()
        _ = self.dispatcher.Handle
        try:
            self.image = Icon(self.icon_path)
            self.menu = ContextMenuStrip()
            for label, handler in [('Open',self._open),('Reload',self._reload),
                                   ('Restart',self._restart),('Close',self._close)]:
                item = self.menu.Items.Add(label)
                item.Click += handler
                setattr(self, label.lower() + '_item', item)
            self.icon = NotifyIcon()
            self.icon.Icon = self.image
            self.icon.Text = 'SoundCloud RPC'
            self.icon.ContextMenuStrip = self.menu
            self.icon.DoubleClick += self._open
            self.icon.Visible = True
            Application.Run(self.context)
        except Exception:
            logging.getLogger(__name__).exception('Tray failed')
        finally:
            if self.icon is not None:
                self.icon.Visible = False
                self.icon.Dispose()
                self.icon = None
            if hasattr(self,'menu'): self.menu.Dispose()
            if hasattr(self,'image'): self.image.Dispose()
            self.dispatcher.Dispose()

    def _install_toolbar(self):
        from System.Windows.Forms import ToolStrip, ToolStripButton, DockStyle, ToolStripItemDisplayStyle, ToolStripGripStyle
        self.form.FormClosing += self._on_closing
        self.form.FormClosed += self._on_closed
        self.toolbar = ToolStrip()
        self.toolbar.Dock = DockStyle.Top
        self.toolbar.GripStyle = ToolStripGripStyle.Hidden
        for label, handler in [('Reload',self._reload),('Restart',self._restart)]:
            button = ToolStripButton(label)
            button.DisplayStyle = ToolStripItemDisplayStyle.Text
            button.Click += handler
            self.toolbar.Items.Add(button)
        self.form.Controls.Add(self.toolbar)
        self.toolbar.SendToBack()

    def _ui(self, action):
        from System import Action
        self.form.BeginInvoke(Action(action))

    def _open(self, *_):
        if self.exiting.is_set(): return
        def show():
            from System.Windows.Forms import FormWindowState
            self.form.Show()
            if self.form.WindowState == FormWindowState.Minimized:
                self.form.WindowState = FormWindowState.Normal
            self.form.Activate()
        self._ui(show)

    def _on_closing(self, sender, args):
        # Respect OS shutdown and Task Manager termination.
        reason = str(getattr(args, 'CloseReason', 'UserClosing'))
        if (reason == 'UserClosing' and not self.exiting.is_set()
                and self.icon and self.icon.Visible):
            args.Cancel = True
            self.form.Hide()

    def _reload(self, *_):
        if self.exiting.is_set(): return
        def reload_page():
            try:
                self.form.browser.webview.CoreWebView2.Reload()
            except Exception:
                logging.getLogger(__name__).exception('Reload failed; use Restart')
        self._ui(reload_page)

    def _restart(self, *_):
        if not self.exiting.is_set():
            self.restart_requested = True
            self._close()

    def _close(self, *_):
        with self.install_lock:
            if self.exiting.is_set(): return
            self.exiting.set()
        self.stop.set()
        threading.Thread(target=self._finish, name='app-shutdown', daemon=True).start()

    def _finish(self):
        if self.restart_requested:
            from recovery import launch_restart
            launch_restart() # New instance waits for this process to end.
        # Only this app's PID is terminated if clean shutdown cannot finish.
        watchdog = threading.Timer(3, lambda: self.force_exit(0))
        watchdog.daemon = True
        watchdog.start()
        try:
            self._ui(self.form.Close)
        except Exception:
            logging.getLogger(__name__).exception('Window close request failed')
        finish_shutdown(self.stop, self.worker, lambda: None)

    def _on_closed(self, *_):
        self.exiting.set()
        self.stop.set()
        if hasattr(self, 'dispatcher') and not self.dispatcher.IsDisposed:
            from System import Action
            self.dispatcher.BeginInvoke(Action(self.context.ExitThread))
