from pathlib import Path
import shutil
import unittest
import uuid

import cv2
import numpy as np

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


if __name__ == "__main__":
    unittest.main()
