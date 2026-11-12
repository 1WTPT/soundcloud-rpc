import threading
import unittest
from recovery import PageReader
from tray import WindowsTray
from types import SimpleNamespace


class RecoveryTests(unittest.TestCase):
    def test_reader_returns_snapshot(self):
        reader = PageReader(lambda: {'playing':True})
        self.assertEqual(reader.read(), {'playing':True})

    def test_hung_page_does_not_block_rpc_or_create_unbounded_threads(self):
        release = threading.Event()
        calls = []
        def stuck():
            calls.append(1)
            release.wait()
        reader = PageReader(stuck, timeout=0.01)
        try:
            for _ in range(3):
                with self.assertRaises(TimeoutError): reader.read()
            self.assertEqual(len(calls),1)
        finally:
            release.set()
            reader.done.wait(1)

    def test_restart_requests_clean_exit(self):
        tray = WindowsTray(None, None, None, 'unused')
        calls=[]
        tray._close=lambda: calls.append('close')
        tray._restart()
        self.assertTrue(tray.restart_requested)
        self.assertEqual(calls,['close'])

    def test_reload_uses_browser_reload(self):
        calls=[]
        tray=WindowsTray(None,None,None,'unused')
        tray.form=SimpleNamespace(browser=SimpleNamespace(webview=SimpleNamespace(
            CoreWebView2=SimpleNamespace(Reload=lambda: calls.append('reload')))))
        tray._reload()
        self.assertEqual(calls,['reload'])
