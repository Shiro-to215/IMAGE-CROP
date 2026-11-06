from pathlib import Path
import shutil
import tkinter as tk
import unittest
import uuid

import cv2
import numpy as np

from app import FrameApp
from video_frames import VideoFrames


class VideoFramesTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(__file__).resolve().parent / ("test-output-" + uuid.uuid4().hex)
        self.directory.mkdir()
        self.addCleanup(shutil.rmtree, self.directory)
        self.path = self.directory / "テスト動画.avi"
        writer = cv2.VideoWriter(str(self.path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
        self.assertTrue(writer.isOpened())
        for value in (20, 60, 100, 140, 180):
            writer.write(np.full((48, 64, 3), value, dtype=np.uint8))
        writer.release()
        self.video = VideoFrames(self.path)
        self.addCleanup(self.video.close)

    def test_forward_backward_and_bounds(self):
        self.assertEqual(self.video.count, 5)
        for index in (0, 1, 4, 2, 1, 0, 3):
            frame = self.video.read(index)
            self.assertEqual(self.video.index, index)
            self.assertAlmostEqual(float(frame.mean()), 20 + index * 40, delta=3)
        self.video.read(-100)
        self.assertEqual(self.video.index, 0)
        self.video.read(100)
        self.assertEqual(self.video.index, 4)

    def test_save_unicode_native_resolution_and_no_overwrite(self):
        self.video.read(3)
        folder = self.directory / "切り出した画像"
        first = self.video.save(folder)
        before = first.read_bytes()
        second = self.video.save(folder)
        self.assertEqual(first.name, "テスト動画_frame_00000004.png")
        self.assertEqual(second.name, "テスト動画_frame_00000004_1.png")
        self.assertEqual(first.read_bytes(), before)
        decoded = cv2.imdecode(np.frombuffer(before, dtype=np.uint8), cv2.IMREAD_COLOR)
        np.testing.assert_array_equal(decoded, self.video.frame)
        self.assertEqual(decoded.shape, (48, 64, 3))

    def test_invalid_video(self):
        with self.assertRaises(ValueError):
            VideoFrames(self.directory / "missing.mp4")

    def test_app_save_preview_and_undo(self):
        root = tk.Tk()
        root.withdraw()
        app = FrameApp(root)
        self.addCleanup(app.close)

        app.video = self.video
        out_dir = self.directory / "app_out"
        app.output.set(str(out_dir))

        app.move_to(3)
        app.save_frame()
        app.move_to(1)
        app.save_frame()
        app.save_frame()  # 重複保存は無視される

        self.assertEqual(app.saved_count, 2)
        self.assertEqual(len(app.saved_items), 2)
        self.assertEqual(app.saved_items[0]["frame_number"], 4)
        self.assertEqual(app.saved_items[1]["frame_number"], 2)
        self.assertEqual(app.preview_title.get(), "保存した画像（2枚）")
        first_path = app.saved_items[0]["path"]
        second_path = app.saved_items[1]["path"]
        self.assertTrue(first_path.exists())
        self.assertTrue(second_path.exists())
        cards = app.preview_inner.winfo_children()
        self.assertEqual(len(cards), 2)
        card_labels = [card.winfo_children()[1].cget("text") for card in cards]
        self.assertEqual(card_labels, ["フレーム 2", "フレーム 4"])

        # Ctrl+Z / undo_save removes the latest saved file (frame 2) and updates preview
        app.key_undo()
        self.assertEqual(app.saved_count, 1)
        self.assertEqual(len(app.saved_items), 1)
        self.assertTrue(first_path.exists())
        self.assertFalse(second_path.exists())
        self.assertEqual(app.preview_title.get(), "保存した画像（1枚）")
        cards = app.preview_inner.winfo_children()
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].winfo_children()[1].cget("text"), "フレーム 4")

        # Second undo removes the remaining saved file
        app.key_undo()
        self.assertEqual(app.saved_count, 0)
        self.assertEqual(len(app.saved_items), 0)
        self.assertFalse(first_path.exists())
        self.assertEqual(app.preview_title.get(), "保存した画像（0枚）")
        self.assertIn("disabled", app.undo_button.state())


if __name__ == "__main__":
    unittest.main()
