import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from faster_whisper import WhisperModel
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate


TIME_RE = re.compile(r"(\d\d):(\d\d):(\d\d),(\d\d\d)")


@dataclass
class SubtitleChunk:
    start: float
    end: float
    text: str


def seconds_to_srt_time(seconds: float) -> str:
    ms_total = int(max(0, seconds) * 1000)
    h = ms_total // 3_600_000
    ms_total %= 3_600_000
    m = ms_total // 60_000
    ms_total %= 60_000
    s = ms_total // 1000
    ms = ms_total % 1000
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def devanagari_to_hinglish(text: str) -> str:
    # DEVANAGARI -> ITRANS -> cleaner Hinglish-like form
    itrans = transliterate(text, sanscript.DEVANAGARI, sanscript.ITRANS)
    # Clean some markers for readability
    clean = (
        itrans.replace(".n", "n")
        .replace(".m", "m")
        .replace("aa", "a")
        .replace("ii", "i")
        .replace("uu", "u")
    )
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def split_segment_to_chunks(start: float, end: float, text: str, max_words: int) -> List[SubtitleChunk]:
    words = text.split()
    if not words:
        return []

    groups: List[List[str]] = []
    for i in range(0, len(words), max_words):
        groups.append(words[i : i + max_words])

    duration = max(0.1, end - start)
    chunk_duration = duration / len(groups)
    chunks: List[SubtitleChunk] = []
    for i, group in enumerate(groups):
        c_start = start + i * chunk_duration
        c_end = min(end, start + (i + 1) * chunk_duration)
        chunks.append(SubtitleChunk(start=c_start, end=c_end, text=" ".join(group)))
    return chunks


def write_srt(chunks: List[SubtitleChunk], out_path: Path) -> None:
    with out_path.open("w", encoding="utf-8") as f:
        for i, chunk in enumerate(chunks, start=1):
            f.write(f"{i}\n")
            f.write(f"{seconds_to_srt_time(chunk.start)} --> {seconds_to_srt_time(chunk.end)}\n")
            f.write(f"{chunk.text}\n\n")


class SubtitleApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Audio to Hinglish Subtitle Generator")
        self.root.geometry("700x460")

        self.audio_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.max_words = tk.IntVar(value=7)
        self.model_size = tk.StringVar(value="small")
        self.device = tk.StringVar(value="cpu")

        self._build_ui()

    def _build_ui(self) -> None:
        frm = ttk.Frame(self.root, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Audio File").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.audio_path, width=65).grid(row=1, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(frm, text="Browse", command=self.pick_audio).grid(row=1, column=1, sticky="ew")

        ttk.Label(frm, text="Output .srt File").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(frm, textvariable=self.output_path, width=65).grid(row=3, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(frm, text="Save As", command=self.pick_output).grid(row=3, column=1, sticky="ew")

        opts = ttk.Frame(frm)
        opts.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(14, 8))

        ttk.Label(opts, text="Whisper Model").grid(row=0, column=0, sticky="w")
        ttk.Combobox(opts, textvariable=self.model_size, values=["tiny", "base", "small", "medium", "large-v3"], width=12, state="readonly").grid(row=1, column=0, sticky="w")

        ttk.Label(opts, text="Device").grid(row=0, column=1, sticky="w", padx=(14, 0))
        ttk.Combobox(opts, textvariable=self.device, values=["cpu", "cuda"], width=8, state="readonly").grid(row=1, column=1, sticky="w", padx=(14, 0))

        ttk.Label(opts, text="Max words per subtitle").grid(row=0, column=2, sticky="w", padx=(14, 0))
        ttk.Spinbox(opts, from_=1, to=20, textvariable=self.max_words, width=5).grid(row=1, column=2, sticky="w", padx=(14, 0))

        ttk.Button(frm, text="Generate Hinglish Subtitles", command=self.start_generation).grid(row=5, column=0, columnspan=2, sticky="ew", pady=10)

        self.progress = tk.Text(frm, height=13)
        self.progress.grid(row=6, column=0, columnspan=2, sticky="nsew")

        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(6, weight=1)

    def log(self, msg: str) -> None:
        self.progress.insert("end", msg + "\n")
        self.progress.see("end")
        self.root.update_idletasks()

    def pick_audio(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3 *.wav *.m4a *.flac *.ogg *.aac"), ("All files", "*.*")])
        if path:
            self.audio_path.set(path)
            if not self.output_path.get():
                self.output_path.set(str(Path(path).with_suffix(".hinglish.srt")))

    def pick_output(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".srt", filetypes=[("SubRip", "*.srt")])
        if path:
            self.output_path.set(path)

    def start_generation(self) -> None:
        if not self.audio_path.get() or not Path(self.audio_path.get()).exists():
            messagebox.showerror("Missing file", "Please select a valid audio file.")
            return

        if not self.output_path.get():
            messagebox.showerror("Missing output", "Please select an output .srt file.")
            return

        if self.max_words.get() < 1:
            messagebox.showerror("Invalid setting", "Max words must be 1 or more.")
            return

        worker = threading.Thread(target=self.generate_subtitles, daemon=True)
        worker.start()

    def generate_subtitles(self) -> None:
        try:
            self.log("Loading Whisper model...")
            model = WhisperModel(self.model_size.get(), device=self.device.get(), compute_type="int8")

            self.log("Transcribing audio in Hindi...")
            segments, info = model.transcribe(self.audio_path.get(), language="hi", vad_filter=True)
            self.log(f"Detected language: {info.language} (prob {info.language_probability:.2f})")

            chunks: List[SubtitleChunk] = []
            for segment in segments:
                roman = devanagari_to_hinglish(segment.text.strip())
                if not roman:
                    continue
                chunks.extend(split_segment_to_chunks(segment.start, segment.end, roman, self.max_words.get()))

            out = Path(self.output_path.get())
            out.parent.mkdir(parents=True, exist_ok=True)
            write_srt(chunks, out)
            self.log(f"Done! Saved: {out}")
            messagebox.showinfo("Success", f"Subtitles generated successfully.\n{out}")
        except Exception as exc:
            self.log(f"Error: {exc}")
            messagebox.showerror("Error", str(exc))


def main() -> None:
    root = tk.Tk()
    app = SubtitleApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
