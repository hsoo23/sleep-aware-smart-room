from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime
import RPi.GPIO as GPIO
from time import sleep
import smtplib
from email.mime.text import MIMEText
import os

app = Flask(__name__)

# =========================
# CORS SETTINGS
# =========================
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


# =========================
# GPIO PIN SETTINGS
# =========================
RELAY_PIN = 17    # GPIO17 = physical pin 11
BUZZER_PIN = 18   # GPIO18 = physical pin 12

GPIO.setmode(GPIO.BCM)

GPIO.setup(BUZZER_PIN, GPIO.OUT)
GPIO.output(BUZZER_PIN, GPIO.LOW)


# =========================
# Gmail SMTP Settings
# 반드시 본인 Gmail + 앱 비밀번호로 수정
# =========================
EMAIL_ADDRESS = "your_gmail@gmail.com"
EMAIL_PASSWORD = "your_gmail_app_password"


# =========================
# Web Config State
# 웹페이지에서 선택한 모드와 이메일 저장
# =========================
current_mode = "sleep"   # "sleep" or "wake"
report_email = ""


# =========================
# Sleep Session State
# =========================
sleep_start_time = None
sleep_actions = []


# =========================
# Relay control
# Open-drain style for active-low relay
# =========================
def relay_on():
    # Lamp ON: pull relay IN to GND
    GPIO.setup(RELAY_PIN, GPIO.OUT)
    GPIO.output(RELAY_PIN, GPIO.LOW)
    print("Relay ON / Lamp ON")


def relay_off():
    # Lamp OFF: release relay IN
    GPIO.setup(RELAY_PIN, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
    print("Relay OFF / Lamp OFF")


# =========================
# Buzzer control
# =========================
def buzzer_alert():
    print("Buzzer alert start")

    for _ in range(5):
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        sleep(0.25)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        sleep(0.25)

    print("Buzzer alert end")


def buzzer_off():
    GPIO.output(BUZZER_PIN, GPIO.LOW)


# =========================
# Email report
# =========================
def send_sleep_report(start_time, end_time, duration_seconds, actions):
    global report_email

    if not report_email:
        print("No report email configured")
        return

    duration_minutes = duration_seconds / 60
    action_text = "\n".join([f"- {action}" for action in actions])

    body = f"""
Sleep-Aware System Report

Mode: Sleep-Aid Mode

Sleep detected time:
{start_time.strftime("%Y-%m-%d %H:%M:%S")}

Wake-up detected time:
{end_time.strftime("%Y-%m-%d %H:%M:%S")}

Estimated sleep duration:
{duration_seconds:.1f} seconds
({duration_minutes:.2f} minutes)

Activated functions:
{action_text}
"""

    msg = MIMEText(body)
    msg["Subject"] = "[Sleep-Aware System] Sleep Report"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = report_email

    print("Sending email from:", EMAIL_ADDRESS)
    print("Sending email to:", report_email)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)

        print("Sleep report email sent")

    except Exception as e:
        print("Failed to send email:", e)


# =========================
# Optional Static Web Routes
# HTML을 서버 주소로 열고 싶을 때 사용 가능
# file:/// 방식이면 필수는 아님
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/styles.css")
def styles():
    return send_from_directory(BASE_DIR, "styles.css")


@app.route("/script.js")
def script():
    return send_from_directory(BASE_DIR, "script.js")


# =========================
# Web Config API
# HTML file에서 mode/email을 저장하는 API
# =========================
@app.route("/set_config", methods=["POST", "OPTIONS"])
def set_config():
    global current_mode, report_email
    global sleep_start_time, sleep_actions

    if request.method == "OPTIONS":
        return jsonify({"ok": True})

    data = request.get_json()

    if data is None:
        return jsonify({
            "ok": False,
            "message": "No JSON data received"
        }), 400

    mode = data.get("mode", "").strip()
    email = data.get("email", "").strip()

    if mode not in ["sleep", "wake"]:
        return jsonify({
            "ok": False,
            "message": "Invalid mode"
        }), 400

    if mode == "sleep" and not email:
        return jsonify({
            "ok": False,
            "message": "Email is required for Sleep Aid Mode"
        }), 400

    current_mode = mode

    if mode == "sleep":
        report_email = email
    else:
        report_email = ""

    # 모드 변경 시 시스템 초기화
    sleep_start_time = None
    sleep_actions = []

    relay_on()
    buzzer_off()

    print("Web config updated")
    print("Mode:", current_mode)
    print("Report email:", report_email)

    return jsonify({
        "ok": True,
        "mode": current_mode,
        "email": report_email
    })


@app.route("/get_config")
def get_config():
    return jsonify({
        "mode": current_mode,
        "email": report_email
    })


# =========================
# Device Control Routes
# =========================
@app.route("/reset")
def reset():
    global sleep_start_time, sleep_actions

    relay_on()
    buzzer_off()

    sleep_start_time = None
    sleep_actions = []

    print("System reset: Lamp ON, Buzzer OFF")

    return "RESET received - lamp on and buzzer off"


@app.route("/wake_drowsy")
def wake_drowsy():
    now = datetime.now()
    print(f"[{now}] WAKE-UP MODE: DROWSY signal received")

    # Wake-Up Mode:
    # Lamp stays ON
    # Buzzer alerts
    relay_on()
    buzzer_alert()

    with open("sleep_log.csv", "a") as f:
        f.write(
            f"{now.strftime('%Y-%m-%d %H:%M:%S')},"
            f"WAKE_MODE,DROWSY,BUZZER_ALERT,LAMP_ON\n"
        )

    return "WAKE mode drowsy received - buzzer alert, lamp stays on"


@app.route("/sleep_start")
def sleep_start():
    global sleep_start_time, sleep_actions

    now = datetime.now()
    sleep_start_time = now
    sleep_actions = []

    print(f"[{now}] SLEEP-AID MODE: Sleep started")

    # Sleep-Aid Mode:
    # Lamp OFF
    # Buzzer does not work
    relay_off()
    buzzer_off()

    sleep_actions.append("Lamp turned off")
    sleep_actions.append("Media playback paused")
    sleep_actions.append("Buzzer was not activated")

    with open("sleep_log.csv", "a") as f:
        f.write(
            f"{now.strftime('%Y-%m-%d %H:%M:%S')},"
            f"SLEEP_MODE,SLEEP_START,LAMP_OFF,MEDIA_PAUSED,BUZZER_OFF\n"
        )

    return "Sleep start received - lamp off"


@app.route("/sleep_end")
def sleep_end():
    global sleep_start_time, sleep_actions

    now = datetime.now()
    print(f"[{now}] SLEEP-AID MODE: Wake-up detected")

    if sleep_start_time is None:
        print("No sleep start time recorded")
        return "No sleep start time recorded"

    duration_seconds = (now - sleep_start_time).total_seconds()

    with open("sleep_log.csv", "a") as f:
        f.write(
            f"{now.strftime('%Y-%m-%d %H:%M:%S')},"
            f"SLEEP_MODE,SLEEP_END,DURATION_SECONDS={duration_seconds:.1f}\n"
        )

    send_sleep_report(
        start_time=sleep_start_time,
        end_time=now,
        duration_seconds=duration_seconds,
        actions=sleep_actions
    )

    sleep_start_time = None
    sleep_actions = []

    return f"Sleep end received - report sent, duration {duration_seconds:.1f} seconds"


@app.route("/light_on")
def light_on():
    relay_on()
    return "Lamp ON"


@app.route("/light_off")
def light_off():
    relay_off()
    return "Lamp OFF"


@app.route("/buzzer")
def buzzer():
    buzzer_alert()
    return "Buzzer alert"


# Legacy test route
@app.route("/drowsy")
def drowsy():
    if current_mode == "wake":
        return wake_drowsy()
    else:
        return sleep_start()


# =========================
# Main
# =========================
if __name__ == "__main__":
    try:
        # 서버 시작 시 무조건 램프 ON, 부저 OFF
        relay_on()
        buzzer_off()

        print("Initial state: Lamp ON, Buzzer OFF")
        app.run(host="0.0.0.0", port=5000)

    finally:
        relay_off()
        buzzer_off()
        GPIO.cleanup()

