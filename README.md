lichess assistant
=============

Platform-independent assistant for [lichess.org](https://lichess.org) in [python](https://www.python.org) using [chrome remote debugging protocol](https://developer.chrome.com/devtools/docs/debugger-protocol).

# Requirements
* [Google Chrome](https://www.google.com/chrome)
* [Python 2.7](https://www.python.org)
  * [python-chess](https://pypi.python.org/pypi/python-chess)
  * [ws4py](https://pypi.python.org/pypi/ws4py)
* [Stockfish](https://stockfishchess.org) (or any UCI-compliant chess engine)

Usage
-----

**Windows**
```
"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 "https://lichess.org/"
```

```
C:\Python27\python.exe lichess.py
```

**Mac OS X**
```
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 "https://lichess.org/" &
```

```
python lichess.py
```

Screenshots
-----------

![](screenshot.png?raw=true)
![](screenshot2.png?raw=true)
