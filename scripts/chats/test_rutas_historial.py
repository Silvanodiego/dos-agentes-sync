import json
import unittest

from rutas_historial import relocate


class RelocationTests(unittest.TestCase):
    def test_cwd_and_projection_offsets_without_editing_messages(self):
        lines = [json.dumps({'type': kind, 'payload': payload}).encode() + b'\r\n' for kind, payload in (
            ('session_meta', {'cwd': 'C:/old'}),
            ('turn_context', {'cwd': 'C:/old/sub'}),
            ('event_msg', {'text': 'C:/old debe conservarse'}))]
        raw = b''.join(lines)
        tables = {'thread_turns': [{'rollout_byte_offset': len(lines[0]), 'rollout_end_byte_offset': len(raw)}],
                  'thread_items': [], 'thread_realtime_items': [],
                  'thread_history_projection_state': [{'next_rollout_byte_offset': len(raw)}]}
        target, adjusted = relocate(raw, tables, 'C:/old', 'D:/usuario/nuevo')
        new_lines = target.splitlines(keepends=True)
        self.assertEqual(json.loads(new_lines[0])['payload']['cwd'].replace('\\', '/'), 'D:/usuario/nuevo')
        self.assertEqual(json.loads(new_lines[1])['payload']['cwd'].replace('\\', '/'), 'D:/usuario/nuevo/sub')
        self.assertEqual(new_lines[2], lines[2])
        self.assertTrue(all(line.endswith(b'\r\n') for line in new_lines))
        self.assertEqual(adjusted['thread_turns'][0]['rollout_byte_offset'], len(new_lines[0]))
        self.assertEqual(adjusted['thread_turns'][0]['rollout_end_byte_offset'], len(target))
        self.assertEqual(adjusted['thread_history_projection_state'][0]['next_rollout_byte_offset'], len(target))
        self.assertEqual(tables['thread_history_projection_state'][0]['next_rollout_byte_offset'], len(raw))

    def test_offset_inside_changed_metadata_is_rejected(self):
        raw = b'{"type":"session_meta","payload":{"cwd":"C:/old"}}\n'
        with self.assertRaisesRegex(ValueError, 'dentro'):
            relocate(raw, {'thread_turns': [{'rollout_byte_offset': 3}], 'thread_history_projection_state': []}, 'C:/old', 'D:/new')


if __name__ == '__main__':
    unittest.main()
