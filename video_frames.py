"""動画のフレーム単位の読み込みと、上書きしないPNG保存。"""

from pathlib import Path

import cv2


class VideoFrames:
    def __init__(self, path):
        self.path = Path(path)
        self.capture = cv2.VideoCapture(str(self.path))
        if not self.capture.isOpened():
            self.capture.release()
            raise ValueError("動画を開けませんでした。形式やファイルの状態を確認してください。")
        self.count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        rate = self.capture.get(cv2.CAP_PROP_FPS)
        self.fps = rate if 0 < rate < 1000 else 30.0
        self.index = -1
        self.frame = None
        try:
            if self.count <= 0:
                raise ValueError("フレーム数を取得できない動画は読み込めません。")
            self.read(0)
        except Exception:
            self.close()
            raise

    def read(self, index):
        index = max(0, min(int(index), self.count - 1))
        if self.frame is not None and index == self.index:
            return self.frame
        if index != self.index + 1:
            if not self.capture.set(cv2.CAP_PROP_POS_FRAMES, index):
                raise ValueError("指定したフレームへ移動できませんでした。")
        ok, frame = self.capture.read()
        if not ok:
            # 次回はシークし直す。表示中のフレームは維持する。
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, self.index + 1)
            raise ValueError(f"フレーム {index + 1} を読み込めませんでした。")
        self.index, self.frame = index, frame
        return frame

    def save(self, directory):
        if self.frame is None:
            raise ValueError("先に動画を読み込んでください。")
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        ok, encoded = cv2.imencode(".png", self.frame)
        if not ok:
            raise ValueError("画像をPNGに変換できませんでした。")
        base = f"{self.path.stem}_frame_{self.index + 1:08d}"
        suffix = 0
        while True:
            name = f"{base}{'_' + str(suffix) if suffix else ''}.png"
            target = directory / name
            try:
                stream = target.open("xb")
            except FileExistsError:
                suffix += 1
                continue
            try:
                with stream:
                    stream.write(encoded.tobytes())
            except Exception:
                target.unlink(missing_ok=True)
                raise
            return target

    def close(self):
        self.capture.release()
