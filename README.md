# Audio to Hinglish Subtitle Generator (GUI)

Yeh desktop tool audio/video se **Hindi subtitles** banata hai aur unko **Hinglish (Roman Hindi)** me output karta hai (`.srt`).

## Features
- Audio se automatic Hindi transcription (Whisper)
- Hinglish (Roman script) subtitle conversion
- **Max words per subtitle** control (GUI se)
- `.srt` export

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> Note: `faster-whisper` ko ffmpeg/ctranslate2 runtime ki zarurat hoti hai. Agar error aaye to system me ffmpeg install karein.

## Run
```bash
python app.py
```

## Use
1. `Browse` se audio file choose karein.
2. `Save As` se output `.srt` location choose karein.
3. `Max words per subtitle` set karein (example: 5, 7, 10).
4. Model choose karein (`small` recommended).
5. `Generate Hinglish Subtitles` click karein.

## Output Example
```srt
1
00:00:00,000 --> 00:00:02,000
namaste dosto aaj hum

2
00:00:02,000 --> 00:00:04,000
ek naya feature dekh rahe hain
```

