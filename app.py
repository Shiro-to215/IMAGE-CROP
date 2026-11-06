"""Windows向け動画フレーム切り出しGUI。python app.py で起動。"""

from pathlib import Path
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2
from PIL import Image, ImageTk

from video_frames import VideoFrames


class FrameApp:
    def __init__(self, root):
        self.root = root
        self.video = None
        self.playing = False
        self.timer = None
        self.resize_timer = None
        self.photo = None
        self.slider_update = False
        self.saved_count = 0
        self.saved_items = []
        self.save_pressed = set()
        self.release_timers = {}
        self.output = tk.StringVar()
        self.video_label = tk.StringVar(value="動画を読み込んでください")
        self.info = tk.StringVar(value="フレーム — / —")
        self.status = tk.StringVar(value="準備完了")
        self.play_label = tk.StringVar(value="▶ 再生")
        self.preview_title = tk.StringVar(value="保存した画像（0枚）")

        root.title("動画フレーム切り出し")
        root.geometry("1100x880")
        root.minsize(760, 660)
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("TButton", padding=(12, 7))
        style.configure("Title.TLabel", font=("Yu Gothic UI", 16, "bold"))

        main = ttk.Frame(root, padding=16)
        main.pack(fill="both", expand=True)
        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="動画フレーム切り出し", style="Title.TLabel").pack(side="left")
        ttk.Button(header, text="動画を開く…", command=self.open_video).pack(side="right")
        ttk.Label(main, textvariable=self.video_label, wraplength=1000).pack(anchor="w", pady=(0, 8))

        output_row = ttk.Frame(main)
        output_row.pack(fill="x", pady=(0, 12))
        ttk.Label(output_row, text="保存先：").pack(side="left")
        ttk.Entry(output_row, textvariable=self.output, state="readonly").pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(output_row, text="変更…", command=self.choose_output).pack(side="left")
        ttk.Button(output_row, text="フォルダーを開く", command=self.reveal_output).pack(side="left", padx=(8, 0))

        self.canvas = tk.Canvas(main, background="#151a23", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self.schedule_render)
        self.canvas.bind("<Button-1>", lambda event: self.canvas.focus_set())
        ttk.Label(main, textvariable=self.info).pack(anchor="w", pady=(10, 0))
        self.slider = ttk.Scale(main, from_=0, to=1, command=self.seek_slider)
        self.slider.pack(fill="x", pady=(4, 8))
        self.slider.state(["disabled"])

        controls = ttk.Frame(main)
        controls.pack(fill="x")
        self.video_buttons = []
        for text, command in [("◀ 前のフレーム", lambda: self.step(-1)),
                              ("次のフレーム ▶", lambda: self.step(1))]:
            button = ttk.Button(controls, text=text, command=command, state="disabled")
            button.pack(side="left", padx=(0, 8))
            self.video_buttons.append(button)
        play = ttk.Button(controls, textvariable=self.play_label, command=self.toggle_play, state="disabled")
        play.pack(side="left")
        save = ttk.Button(controls, text="画像を保存  (Shift / Enter)", command=self.save_frame, state="disabled")
        save.pack(side="right")
        self.undo_button = ttk.Button(controls, text="保存を取り消す  (Ctrl+Z)", command=self.undo_save, state="disabled")
        self.undo_button.pack(side="right", padx=(0, 8))
        self.video_buttons.extend([play, save])
        ttk.Label(main, text="← / →：1フレーム移動    Shift / Enter：PNG保存    Ctrl+Z：保存取り消し    Space：再生・一時停止    Ctrl+O：動画を開く").pack(anchor="w", pady=(12, 4))
        ttk.Label(main, textvariable=self.status, wraplength=1020).pack(anchor="w")

        preview_section = ttk.Frame(main)
        preview_section.pack(fill="x", pady=(10, 0))
        ttk.Label(preview_section, textvariable=self.preview_title).pack(anchor="w", pady=(0, 4))
        self.preview_canvas = tk.Canvas(preview_section, height=110, background="#1e2430", highlightthickness=0)
        self.preview_canvas.pack(fill="x")
        self.preview_scrollbar = ttk.Scrollbar(preview_section, orient="horizontal", command=self.preview_canvas.xview)
        self.preview_scrollbar.pack(fill="x")
        self.preview_canvas.configure(xscrollcommand=self.preview_scrollbar.set)
        self.preview_inner = tk.Frame(self.preview_canvas, background="#1e2430")
        self.preview_window = self.preview_canvas.create_window((0, 0), window=self.preview_inner, anchor="nw")
        self.preview_inner.bind("<Configure>", self._on_preview_configure)
        self.preview_canvas.bind("<Configure>", self._on_preview_configure)
        self.update_preview_strip()

        root.bind("<Left>", lambda event: self.key_step(-1))
        root.bind("<Right>", lambda event: self.key_step(1))
        root.bind("<space>", lambda event: self.key_play())
        root.bind("<Control-o>", lambda event: self.open_video())
        root.bind("<Control-z>", self.key_undo)
        root.bind("<Control-Z>", self.key_undo)
        for key in ("Shift_L", "Shift_R", "Return", "KP_Enter"):
            root.bind(f"<KeyPress-{key}>", self.key_save)
            root.bind(f"<KeyRelease-{key}>", self.release_save)
        root.bind("<FocusOut>", self.focus_out)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def open_video(self):
        self.pause()
        path = filedialog.askopenfilename(title="動画ファイルを選択", filetypes=[
            ("動画ファイル", "*.mp4 *.avi *.mov *.mkv *.wmv *.m4v *.webm *.mts *.m2ts"),
            ("すべてのファイル", "*.*")])
        if not path:
            return
        try:
            video = VideoFrames(path)
        except Exception as error:
            messagebox.showerror("読み込みエラー", str(error))
            return
        if self.video:
            self.video.close()
        self.video = video
        self.video_label.set(str(video.path))
        if not self.output.get():
            self.output.set(str(video.path.parent / f"{video.path.stem}_frames"))
        self.saved_count = 0
        self.saved_items.clear()
        self.update_preview_strip()
        self.slider_update = True
        self.slider.configure(to=max(1, video.count - 1))
        self.slider.set(0)
        self.slider_update = False
        self.slider.state(["!disabled"])
        for button in self.video_buttons:
            button.state(["!disabled"])
        self.status.set("読み込み完了。左右キーでフレームを選び、Shift / Enterで保存できます。")
        self.update_frame()
        self.canvas.focus_set()

    def choose_output(self):
        self.pause()
        path = filedialog.askdirectory(title="画像の保存先フォルダー", mustexist=False)
        if path:
            self.output.set(path)
        self.canvas.focus_set()

    def reveal_output(self):
        if not self.output.get():
            return
        try:
            path = Path(self.output.get())
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(str(path))
        except Exception as error:
            messagebox.showerror("フォルダーを開けません", str(error))

    def move_to(self, index):
        if not self.video:
            return
        try:
            self.video.read(index)
        except Exception as error:
            self.pause()
            messagebox.showerror("フレーム読み込みエラー", str(error))
        self.update_frame()

    def step(self, delta):
        self.pause()
        if self.video:
            self.move_to(self.video.index + delta)

    def key_step(self, delta):
        self.step(delta)
        return "break"

    def key_play(self):
        self.toggle_play()
        return "break"

    def seek_slider(self, value):
        if not self.slider_update and self.video:
            self.pause()
            self.move_to(round(float(value)))

    def update_frame(self):
        video = self.video
        self.slider_update = True
        self.slider.set(video.index)
        self.slider_update = False
        height, width = video.frame.shape[:2]
        seconds = video.index / video.fps
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(int(minutes), 60)
        self.info.set(f"フレーム {video.index + 1:,} / {video.count:,}    |    {hours:02d}:{minutes:02d}:{seconds:06.3f}    |    {width} × {height}    |    {video.fps:.3f} fps")
        self.render()

    def schedule_render(self, event=None):
        if self.resize_timer:
            self.root.after_cancel(self.resize_timer)
        self.resize_timer = self.root.after(60, self.render)

    def render(self):
        if self.resize_timer:
            self.root.after_cancel(self.resize_timer)
            self.resize_timer = None
        self.canvas.delete("all")
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if not self.video:
            self.canvas.create_text(width // 2, height // 2, text="「動画を開く」からファイルを選択", fill="#cbd5e1", font=("Yu Gothic UI", 16))
            return
        picture = Image.fromarray(cv2.cvtColor(self.video.frame, cv2.COLOR_BGR2RGB))
        picture.thumbnail((max(1, width), max(1, height)), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(picture)
        self.canvas.create_image(width // 2, height // 2, image=self.photo)

    def toggle_play(self):
        if not self.video:
            return
        if self.playing:
            self.pause()
        else:
            if self.video.index == self.video.count - 1:
                self.move_to(0)
            self.playing = True
            self.play_label.set("Ⅱ 一時停止")
            self.timer = self.root.after(max(1, round(1000 / self.video.fps)), self.tick)

    def tick(self):
        self.timer = None
        if not self.playing:
            return
        if self.video.index >= self.video.count - 1:
            self.pause()
            return
        self.move_to(self.video.index + 1)
        if self.playing:
            self.timer = self.root.after(max(1, round(1000 / self.video.fps)), self.tick)

    def pause(self):
        self.playing = False
        self.play_label.set("▶ 再生")
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None

    def key_save(self, event):
        pending = self.release_timers.pop(event.keysym, None)
        if pending is not None:
            self.root.after_cancel(pending)
        if event.keysym not in self.save_pressed:
            self.save_pressed.add(event.keysym)
            self.save_frame()
        return "break"

    def release_save(self, event):
        key = event.keysym
        self.release_timers[key] = self.root.after_idle(lambda: self.clear_key(key))
        return "break"

    def clear_key(self, key):
        self.save_pressed.discard(key)
        self.release_timers.pop(key, None)

    def focus_out(self, event):
        if self.root.focus_displayof() is None:
            self.save_pressed.clear()
            self.pause()

    def save_frame(self):
        if not self.video:
            return
        self.pause()
        if any(item["index"] == self.video.index for item in self.saved_items):
            return
        if not self.output.get():
            self.choose_output()
            if not self.output.get():
                return
        try:
            target = self.video.save(self.output.get())
        except Exception as error:
            messagebox.showerror("保存エラー", str(error))
            return
        thumb = Image.fromarray(cv2.cvtColor(self.video.frame, cv2.COLOR_BGR2RGB))
        thumb.thumbnail((116, 68), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(thumb)
        new_item = {
            "path": target,
            "index": self.video.index,
            "frame_number": self.video.index + 1,
            "photo": photo,
        }
        self.saved_items.append(new_item)
        self.saved_count = len(self.saved_items)
        self.update_preview_strip(focus_item=new_item)
        self.status.set(f"保存しました（{self.saved_count}枚）：{target.name}")

    def key_undo(self, event=None):
        self.undo_save()
        return "break"

    def undo_save(self):
        if not self.saved_items:
            self.status.set("取り消せる保存画像はありません。")
            return
        self.pause()
        item = self.saved_items[-1]
        try:
            item["path"].unlink(missing_ok=True)
        except Exception as error:
            messagebox.showerror("取り消しエラー", str(error))
            return
        self.saved_items.pop()
        self.saved_count = len(self.saved_items)
        self.update_preview_strip()
        self.status.set(f"保存を取り消しました（残り{self.saved_count}枚）：{item['path'].name}")

    def _on_preview_configure(self, event=None):
        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

    def update_preview_strip(self, focus_item=None):
        self.preview_title.set(f"保存した画像（{len(self.saved_items)}枚）")
        if self.saved_items:
            self.undo_button.state(["!disabled"])
        else:
            self.undo_button.state(["disabled"])

        for child in self.preview_inner.winfo_children():
            child.destroy()

        focus_card = None
        if not self.saved_items:
            empty = tk.Label(
                self.preview_inner,
                text="保存した画像のプレビュー（画像・フレーム数）がここに表示されます",
                bg="#1e2430",
                fg="#94a3b8",
                font=("Yu Gothic UI", 10),
                padx=16,
                pady=40,
            )
            empty.pack(side="left")
        else:
            ordered_items = sorted(self.saved_items, key=lambda item: item["index"])
            for item in ordered_items:
                card = tk.Frame(self.preview_inner, bg="#283142", padx=6, pady=6, cursor="hand2")
                card.pack(side="left", padx=(6, 0), pady=6)
                if item is focus_item:
                    focus_card = card
                img_label = tk.Label(card, image=item["photo"], bg="#151a23", width=116, height=68)
                img_label.pack()
                txt_label = tk.Label(
                    card,
                    text=f"フレーム {item['frame_number']:,}",
                    bg="#283142",
                    fg="#e2e8f0",
                    font=("Yu Gothic UI", 9, "bold"),
                )
                txt_label.pack(pady=(4, 0))
                idx = item["index"]
                for widget in (card, img_label, txt_label):
                    widget.bind("<Button-1>", lambda e, target_idx=idx: self._jump_from_preview(target_idx))

        self.preview_inner.update_idletasks()
        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))
        if focus_card is not None:
            total_width = max(1, self.preview_inner.winfo_reqwidth())
            canvas_width = max(1, self.preview_canvas.winfo_width())
            if total_width > canvas_width:
                card_left = focus_card.winfo_x()
                card_right = card_left + focus_card.winfo_reqwidth()
                target_x = max(0, min(card_right - canvas_width + 12, total_width - canvas_width))
                if card_left < target_x:
                    target_x = max(0, card_left - 12)
                self.preview_canvas.xview_moveto(target_x / total_width)

    def _jump_from_preview(self, index):
        self.pause()
        self.move_to(index)
        self.canvas.focus_set()

    def close(self):
        self.pause()
        if self.video:
            self.video.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    FrameApp(root)
    root.mainloop()
