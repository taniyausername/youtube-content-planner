# Run the project on your own computer

You do not need GitHub, Render, Docker or an API key for the demo.

1. Install Python 3.12 from https://www.python.org/downloads/ if it is not already installed.
2. Extract the ZIP. Open a terminal inside the extracted `youtube-content-planner` folder.
3. On a Mac or Linux, run:

```sh
python3 start.py
```

On Windows, double-click `Start_Windows.bat` or run:

```bat
py -3.12 start.py
```

The launcher creates an isolated Python environment, installs dependencies on its first run, creates `.env` only if it does not exist, starts the app and opens your browser. The first run needs internet access; subsequent demo runs use the installed dependencies.

The local address is **http://127.0.0.1:8000**. It becomes available after the launcher prints `App is ready`. Keep the terminal open while using the app. Press **Ctrl+C** to stop it.

If you have multiple Python versions on your Mac, use `python3.12 start.py`. If port 8000 is busy, run `python3 start.py --port 8001` and open the address printed by the launcher.

On macOS, you can also use `Start_Mac.command` after granting execute permission with `chmod +x Start_Mac.command`. The `python3 start.py` method avoids that extra step.

Your research is stored in the local `data` folder. Demo mode uses clearly labelled synthetic records. To collect real YouTube metadata, follow the server-key setup in README.md; keep the key in `.env` and restart the app.

This package has been checked in a Linux workspace. The launcher has not been executed on your personal Mac or on Windows. Opening a localhost link before starting it on your computer will not work.
