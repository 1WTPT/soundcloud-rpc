import threading
import unittest
from types import SimpleNamespace
from tray import WindowsTray, finish_shutdown


class TrayTests(unittest.TestCase):
    def test_window_close_hides_without_stopping_music(self):
        calls = []
        stop = threading.Event()
        tray = WindowsTray(None, stop, None, 'unused.ico')
        tray.form = SimpleNamespace(Hide=lambda: calls.append('hide'))
        tray.icon = SimpleNamespace(Visible=True)
        args = SimpleNamespace(Cancel=False)
        tray._on_closing(None, args)
        self.assertTrue(args.Cancel)
        self.assertEqual(calls, ['hide'])
        self.assertFalse(stop.is_set())

    def test_exit_allows_real_close(self):
        tray = WindowsTray(None, threading.Event(), None, 'unused.ico')
        tray.exiting.set()
        args = SimpleNamespace(Cancel=False)
        tray._on_closing(None, args)
        self.assertFalse(args.Cancel)

    def test_rpc_cleanup_precedes_browser_destruction(self):
        calls = []
        stop = threading.Event()
        def run():
            try:
                stop.wait()
            finally:
                calls.extend(['rpc.clear', 'rpc.close'])
        worker = threading.Thread(target=run)
        worker.start()
        finish_shutdown(stop, worker, lambda: calls.append('destroy'))
        self.assertFalse(worker.is_alive())
        self.assertEqual(calls, ['rpc.clear', 'rpc.close', 'destroy'])

    def test_stuck_worker_cannot_prevent_exit_forever(self):
        calls = []
        worker = SimpleNamespace(ident=1, join=lambda timeout: calls.append(timeout))
        finish_shutdown(threading.Event(), worker, lambda: calls.append('destroy'))
        self.assertEqual(calls, [8, 'destroy'])
