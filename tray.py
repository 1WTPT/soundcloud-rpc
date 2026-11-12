"""Independent STA message loop keeps the tray usable when the browser hangs."""
import logging
import os
import threading
from pathlib import Path


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
        from System.Drawing import Color, Font
        from System.Windows.Forms import (ToolStrip, ToolStripButton, DockStyle,
            ToolStripItemDisplayStyle, ToolStripGripStyle, ToolStripProfessionalRenderer, Padding)
        self.form.FormClosing += self._on_closing
        self.form.FormClosed += self._on_closed
        self.toolbar = ToolStrip()
        self.toolbar.Dock = DockStyle.Top
        self.toolbar.GripStyle = ToolStripGripStyle.Hidden
        self.toolbar.AutoSize = False
        self.toolbar.Height = 30
        self.toolbar.Padding = Padding(8, 2, 8, 2)
        self.toolbar.BackColor = Color.FromArgb(23, 23, 23)
        self.toolbar.ForeColor = Color.FromArgb(184, 184, 184)
        try:
            import ctypes
            from System.Drawing.Text import PrivateFontCollection
            path = Path(self.icon_path).parent / 'fonts' / 'Nunito-Regular.ttf'
            # ToolStrip uses GDI for text; register only within this process,
            # and retain the GDI+ collection for the Font object's lifetime.
            add_font = ctypes.windll.gdi32.AddFontResourceExW
            add_font.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
            add_font.restype = ctypes.c_int
            if not add_font(str(path), 0x10, None):
                raise OSError('Could not load bundled Nunito font')
            self.toolbar_fonts = PrivateFontCollection()
            self.toolbar_fonts.AddFontFile(str(path))
            self.toolbar.Font = Font(self.toolbar_fonts.Families[0], 10)
        except Exception:
            logging.getLogger(__name__).exception('Toolbar font unavailable')
            self.toolbar.Font = Font('Segoe UI', 10)
        self.toolbar_renderer = ToolStripProfessionalRenderer()
        self.toolbar_renderer.RoundedEdges = False
        self.toolbar_renderer.RenderToolStripBackground += self._paint_toolbar_background
        self.toolbar_renderer.RenderToolStripBorder += self._paint_toolbar_border
        self.toolbar_renderer.RenderButtonBackground += self._paint_toolbar_button
        self.toolbar.Renderer = self.toolbar_renderer
        for label, handler in [('Reload',self._reload),('Restart',self._restart)]:
            button = ToolStripButton(label)
            button.DisplayStyle = ToolStripItemDisplayStyle.Text
            button.ForeColor = self.toolbar.ForeColor
            button.Padding = Padding(8, 0, 8, 0)
            button.Margin = Padding(0, 0, 4, 0)
            button.Click += handler
            self.toolbar.Items.Add(button)
        self.form.Controls.Add(self.toolbar)
        self.toolbar.SendToBack()

    def _paint_toolbar_background(self, sender, args):
        from System.Drawing import SolidBrush
        brush = SolidBrush(self.toolbar.BackColor)
        try:
            args.Graphics.FillRectangle(brush, self.toolbar.ClientRectangle)
        finally:
            brush.Dispose()

    def _paint_toolbar_border(self, sender, args):
        from System.Drawing import Color, Pen
        pen = Pen(Color.FromArgb(38, 38, 38))
        try:
            args.Graphics.DrawLine(pen, 0, self.toolbar.Height - 1,
                                   self.toolbar.Width, self.toolbar.Height - 1)
        finally:
            pen.Dispose()

    def _paint_toolbar_button(self, sender, args):
        from System.Drawing import Color, SolidBrush, Rectangle
        item = args.Item
        shade = 55 if item.Pressed else 39 if item.Selected else 23
        brush = SolidBrush(Color.FromArgb(shade, shade, shade))
        try:
            args.Graphics.FillRectangle(brush, Rectangle(0, 0, item.Width, item.Height))
        finally:
            brush.Dispose()

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
