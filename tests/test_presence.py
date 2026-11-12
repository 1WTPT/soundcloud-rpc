import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from presence import PresenceController, Track, track_from_snapshot


class FakeRPC:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def connect(self):
        if self.fail:
            raise ConnectionError('Discord closed')
        self.calls.append('connect')

    def clear(self):
        self.calls.append('clear')

    def update(self, **fields):
        self.calls.append(fields)

    def close(self):
        self.calls.append('close')


class Tests(unittest.TestCase):
    def test_paused_missing_and_malformed(self):
        for data in (None, [], {}, {'playing': False, 'title': 'Song'},
                     {'playing': True, 'title': 7}):
            self.assertIsNone(track_from_snapshot(data))

    def test_urls_and_unicode_limits(self):
        track = track_from_snapshot({'playing': True, 'title': 'Я' * 150,
            'artist': 'Artist', 'url': 'https://soundcloud.com.evil.test/a/b',
            'artwork': 'file:///C:/private.jpg'})
        self.assertLessEqual(len(track.title.encode()), 120)
        self.assertEqual(track.url, '')
        self.assertEqual(track.artwork, '')
        self.assertNotIn('buttons', track.fields())

    def test_public_cover_and_button(self):
        track = track_from_snapshot({'playing': True, 'title': 'A',
            'artwork': 'https://i1.sndcdn.com/art.jpg',
            'url': 'https://soundcloud.com/artist/track'})
        self.assertEqual(track.fields()['large_image'], 'https://i1.sndcdn.com/art.jpg')
        self.assertEqual(track.fields()['details'], 'A ')
        self.assertIn('buttons', track.fields())

    def test_track_change_pause_resume_and_close(self):
        rpc = FakeRPC()
        clock = [0]
        controller = PresenceController(lambda: rpc, lambda: clock[0])
        first = Track('First', 'Artist')
        controller.tick(first)
        controller.tick(first)
        self.assertEqual(sum(isinstance(c, dict) for c in rpc.calls), 1)
        clock[0] = 6
        controller.tick(Track('Second', 'Artist'))
        clock[0] = 12
        controller.tick(None)
        self.assertEqual(rpc.calls[-1], 'clear')
        clock[0] = 18
        controller.tick(first)
        self.assertEqual(rpc.calls[-1]['details'], 'First')
        controller.close()
        self.assertEqual(rpc.calls[-2:], ['clear', 'close'])

    def test_retry_and_restore_after_discord_restart(self):
        bad, good = FakeRPC(fail=True), FakeRPC()
        clients = iter((bad, good))
        clock = [0]
        controller = PresenceController(lambda: next(clients), lambda: clock[0])
        track = Track('Song', 'Artist')
        controller.tick(track)
        self.assertIsNone(controller.rpc)
        clock[0] = 4
        controller.tick(track)
        self.assertEqual(good.calls, [])
        clock[0] = 10
        controller.tick(track)
        self.assertEqual(good.calls[-1]['details'], 'Song')

    def test_latest_track_wins_during_throttle(self):
        rpc = FakeRPC()
        clock = [0]
        controller = PresenceController(lambda: rpc, lambda: clock[0])
        controller.tick(Track('First', 'Artist'))
        clock[0] = 2
        controller.tick(Track('Skipped', 'Artist'))
        clock[0] = 6
        controller.tick(Track('Current', 'Artist'))
        self.assertEqual(rpc.calls[-1]['details'], 'Current')
        self.assertFalse(any(isinstance(c, dict) and c['details'] == 'Skipped' for c in rpc.calls))

    def test_heartbeat_detects_disconnect_without_track_change(self):
        rpc = FakeRPC()
        clock = [0]
        controller = PresenceController(lambda: rpc, lambda: clock[0])
        track = Track('Song', 'Artist')
        controller.tick(track)
        def disconnected(**_):
            raise ConnectionError('Discord restarted')
        rpc.update = disconnected
        clock[0] = 30
        controller.tick(track)
        self.assertIsNone(controller.rpc)


if __name__ == '__main__':
    unittest.main()
