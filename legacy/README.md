# AI-Based Sleep-Aware Smart Room System

## 1. File Roles

- `main.py`  
  Runs camera-based drowsiness detection on the Host PC.  
  It sends requests to the Raspberry Pi server and controls YouTube playback.

- `pi_server.py`  
  Runs on the Raspberry Pi.  
  It controls the relay lamp, buzzer, mode settings, and sleep report email.

- `launcher_server.py`  
  Runs on the Host PC.  
  It starts `main.py` when the web page button is clicked.

- `index.html`, `styles.css`, `script.js`  
  Web interface for selecting Sleep Aid Mode / Wake-up Mode and entering the report email.

## 2. Values That Must Be Changed Before Running

This project contains several environment-specific values.  
Each user must modify them according to their own setup.

### 1) Raspberry Pi SSH address

In the command below, replace the username and host address with your own Raspberry Pi SSH information.

```bash
ssh -L 5050:127.0.0.1:5000 YOUR_PI_USERNAME@YOUR_PI_HOST
```

Example:

```bash
ssh -L 5050:127.0.0.1:5000 pi@raspberrypi.local
```

If `.local` does not work, use the Raspberry Pi IP address instead.

```bash
ssh -L 5050:127.0.0.1:5000 pi@192.168.0.10
```

### 2) Raspberry Pi server URL

If SSH tunneling is used, keep these values:

In `main.py`:

```python
PI_URL = "http://127.0.0.1:5050"
```

In `script.js`:

```javascript
const API_BASE = "http://127.0.0.1:5050";
```

If SSH tunneling is not used, replace them with the Raspberry Pi IP address.

Example:

```python
PI_URL = "http://192.168.0.10:5000"
```

```javascript
const API_BASE = "http://192.168.0.10:5000";
```

### 3) Host PC project path

In `launcher_server.py`, replace the project path with your own local folder path.

```python
PROJECT_DIR = "/path/to/project_iot"
```

Example:

```python
PROJECT_DIR = "/Users/username/project_iot"
```

### 4) Conda environment name

In `launcher_server.py`, replace the conda environment name if needed.

```python
CONDA_ENV = "iot"
```

If your environment name is different, change it.

Example:

```python
CONDA_ENV = "myenv"
```

### 5) Gmail sender information

In `pi_server.py`, replace the sender Gmail address and Gmail app password.

```python
EMAIL_ADDRESS = "your_gmail@gmail.com"
EMAIL_PASSWORD = "your_gmail_app_password"
```

The password must be a Gmail app password, not the normal Gmail login password.  
Do not submit or share the actual app password publicly.

The receiver email is entered through the web page in Sleep Aid Mode.

## 3. Required Packages

Host PC:

```bash
pip install opencv-python mediapipe numpy requests flask pyautogui
```

Raspberry Pi:

```bash
pip install flask RPi.GPIO
```

## 4. How to Run

### Step 1. Run Raspberry Pi server

On Raspberry Pi:

```bash
python pi_server.py
```

### Step 2. Open SSH tunnel

On Host PC:

```bash
ssh -L 5050:127.0.0.1:5000 YOUR_PI_USERNAME@YOUR_PI_HOST
```

Keep this terminal open.

### Step 3. Run launcher server

On Host PC:

```bash
python launcher_server.py
```

Expected address:

```text
http://127.0.0.1:7000
```

### Step 4. Open web page

Open `index.html` in Google Chrome.

### Step 5. Select mode

- Sleep Aid Mode: enter report email and click Enable alerts.
- Wake-up Mode: click the Wake-up button.

After selecting a mode, `main.py` starts automatically and the camera detection window opens.

## 6. Notes

- YouTube control uses AppleScript, so the current media control function is designed for macOS.
- Chrome must allow JavaScript from Apple Events.
- Gmail email reporting requires a valid Gmail app password.
- Personal values such as SSH address, local project path, Gmail address, and app password must be changed before running.
