# vosk-audio-profanity-detector-app
PyQt5 GUI program which detects bad words from an audio file with vosk api

## install dependencies
```sh
pip install -r requirements/base.txt
```

## download vosk model
You can visit ttps://alphacephei.com/vosk/models and download models for each languages.
Extract downloaded model to root folder as "model"

## building for development
Copy model and ffmpeg.exe in src/freeze to root path
```sh
fbs run
```

## make an executable
Make folder src/freeze/windows for Windows. You can check fbs guide for other platforms.
Copy model folder, ffmpeg.exe to src/freeze/windows
Then, find vosk dlls located in .venv/Lib/site-packages/vosk and copy vosk folder to src/freeze/windows
```sh
fbs freeze
```

## make an installer
```sh
fbs installer
```
