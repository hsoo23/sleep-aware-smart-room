from flask import Flask, jsonify
import subprocess
import os
import signal

app = Flask(__name__)

# main.py가 있는 폴더
PROJECT_DIR = "/path/to/project_iot"

# conda 환경 이름
CONDA_ENV = "your_conda_env_name"

process = None


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/")
def home():
    return "MacBook launcher server is running"


@app.route("/start_detection")
def start_detection():
    global process

    if process is not None and process.poll() is None:
        return jsonify({
            "ok": True,
            "message": "main.py is already running"
        })

    command = f'''
    cd "{PROJECT_DIR}"
    source /opt/anaconda3/etc/profile.d/conda.sh
    conda activate {CONDA_ENV}
    python main.py
    '''

    process = subprocess.Popen(
        ["bash", "-lc", command],
        cwd=PROJECT_DIR
    )

    return jsonify({
        "ok": True,
        "message": "main.py started"
    })


@app.route("/stop_detection")
def stop_detection():
    global process

    if process is not None and process.poll() is None:
        os.kill(process.pid, signal.SIGTERM)
        process = None

        return jsonify({
            "ok": True,
            "message": "main.py stopped"
        })

    return jsonify({
        "ok": True,
        "message": "main.py was not running"
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=7000)
