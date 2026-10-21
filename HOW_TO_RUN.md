# How to run PassTune

PassTune is a local website. It runs on your own laptop and opens in the
browser. You need an internet connection once, for the setup. After that it
works offline.

Unzip the project somewhere with a short path, such as the Desktop. Do not
run it from inside the zip.

---

## macOS (MacBook, Apple Silicon or Intel)

**One-time setup** takes about 10–15 minutes, mostly downloads.

1. Open **Terminal**: press ⌘ Space, type `Terminal`, press Enter.
2. Go to the project folder. Type `cd ` (with a space), drag the
   `bo-compiler-opt` folder from Finder into the Terminal window, and press Enter.
3. Run the setup script:

   ```bash
   bash setup_mac.sh
   ```

   The script does the following:
   - **Command line tools.** If Apple's command line tools are missing, a
     dialog opens. Click **Install**, wait until it finishes, then run
     `bash setup_mac.sh` again.
   - **Homebrew.** If Homebrew is missing, the script prints a one-line
     command to install it. Paste that command, press Enter, enter the Mac
     password when asked, then run `bash setup_mac.sh` again.
   - **GCC.** It installs GCC with Homebrew. On a Mac, `gcc` is really Apple
     clang, which does not support GCC's optimization passes.
   - **Python.** It creates a Python environment and installs the packages.
   - **Self-check.** It builds and runs all 9 benchmarks and checks their
     output. It must end with **All checks passed**.

**Start the website**, every time:

```bash
bash run_mac.sh
```

The browser opens at **http://127.0.0.1:5050**. To stop the website, press
Ctrl+C in the Terminal window. The Mac uses port 5050 because macOS keeps
port 5000 for AirPlay.

---

## Windows

1. **Install Python 3.12** from https://www.python.org/downloads/. During
   installation, tick **Add python.exe to PATH**.
2. **Install GCC.** Download the WinLibs **GCC UCRT, Win64** zip from
   https://winlibs.com/ and extract it so that `C:\mingw64\bin\gcc.exe`
   exists.
3. **Run the setup.** Double-click **`setup_windows.bat`**. It must end with
   **All checks passed**.
4. **Start the website.** Double-click **`run_windows.bat`**. The browser
   opens at **http://127.0.0.1:5000**. To stop the website, close the black
   window.

Keep the folder in a short path, such as `C:\proj\bo-compiler-opt`. Windows
cannot load programs from very long paths.

---

## Checking an installation

```bash
.venv/bin/python scripts/check_setup.py              # macOS
.venv\Scripts\python scripts\check_setup.py          # Windows
```

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Website shows "GCC was not found" | macOS: `brew install gcc`, then run `bash setup_mac.sh` again. Windows: install GCC to `C:\mingw64` and run the setup again. |
| "Address already in use" | Another copy is already running. Close it, or start on another port: `PORT=5060 bash run_mac.sh` |
| `pip install` fails | Check the internet connection and run the setup again. If pinned versions are not available, the script installs the latest compatible ones. |
| Self-check says a benchmark output "differs from reference" | The setup already passes `--fix-references`, which stores this machine's reference output. Run the setup again. |
| Mac blocks a file "from an unidentified developer" | Start the scripts with `bash …` as shown above, not by double-clicking. |
| A run is very slow | Plug in the charger and close heavy apps. Timings are noisy on battery saver. |

## What is included

- **Study results** in `results/`: 2,700 evaluations and the final
  measurements, all from the original Windows laptop (GCC 16.1). The
  Results, Compare methods and Runs pages show these results on any
  machine, even without GCC.
- **Live optimizations** started from the website run on the machine you
  are using. On a MacBook (a different CPU and GCC build), the speed-ups will
  differ from the study numbers. That is expected: the best flag
  configuration depends on the machine, which is why the search is done
  per program and per machine.
