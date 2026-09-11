import cv2
import mediapipe as mp
import numpy as np
import requests
import pyautogui
import time
import subprocess

# =========================
# Raspberry Pi Server
# =========================
PI_URL = "http://127.0.0.1:5050"


def send_request(endpoint):
    try:
        # 이메일 전송, 부저 동작은 시간이 걸릴 수 있어서 timeout을 길게 설정
        response = requests.get(f"{PI_URL}/{endpoint}", timeout=20)
        print(f"Sent /{endpoint} to Raspberry Pi:", response.text)
        return response.text
    except Exception as e:
        print(f"Failed to send /{endpoint}:", e)
        return None


def get_web_config():
    try:
        response = requests.get(f"{PI_URL}/get_config", timeout=2)
        data = response.json()

        mode = data.get("mode", "sleep")
        email = data.get("email", "")

        print("Loaded web config")
        print("Mode:", mode)
        print("Email:", email)

        return mode, email

    except Exception as e:
        print("Failed to load web config:", e)
        print("Default mode: sleep")
        return "sleep", ""


# =========================
# YouTube Control - Google Chrome
# =========================
def pause_youtube():
    try:
        script = '''
        tell application "Google Chrome"
            repeat with w in windows
                set tabIndex to 0
                repeat with t in tabs of w
                    set tabIndex to tabIndex + 1
                    if URL of t contains "youtube.com" then
                        set active tab index of w to tabIndex
                        set index of w to 1
                        tell t
                            execute javascript "var v = document.querySelector('video'); if (v) { v.pause(); 'paused'; } else { 'no video'; }"
                        end tell
                        return "paused"
                    end if
                end repeat
            end repeat
            return "no youtube tab"
        end tell
        '''

        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True
        )

        print("YouTube pause result:", result.stdout.strip())

    except Exception as e:
        print("Failed to pause YouTube:", e)


def play_youtube():
    try:
        script = '''
        tell application "Google Chrome"
            repeat with w in windows
                set tabIndex to 0
                repeat with t in tabs of w
                    set tabIndex to tabIndex + 1
                    if URL of t contains "youtube.com" then
                        set active tab index of w to tabIndex
                        set index of w to 1
                        tell t
                            execute javascript "var v = document.querySelector('video'); if (v) { v.play(); 'playing'; } else { 'no video'; }"
                        end tell
                        return "playing"
                    end if
                end repeat
            end repeat
            return "no youtube tab"
        end tell
        '''

        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True
        )

        print("YouTube play result:", result.stdout.strip())

    except Exception as e:
        print("Failed to play YouTube:", e)


def pause_media():
    try:
        pyautogui.press("space")
        print("Media pause command sent")
    except Exception as e:
        print("Failed to pause media:", e)


# =========================
# Load Web Config
# =========================
MODE, REPORT_EMAIL = get_web_config()

if MODE not in ["sleep", "wake"]:
    MODE = "sleep"

print("Selected Mode:", MODE)

# 코드 시작 시 무조건 램프 ON + 부저 OFF
send_request("reset")

# =========================
# MediaPipe Face Mesh Setting
# =========================
mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# EAR 계산에 사용할 왼쪽/오른쪽 눈 랜드마크 번호
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

# 눈 감김 판단 기준값
EAR_THRESHOLD = 0.21

# 화면에 DROWSY로 표시되는 기준
DROWSY_STATUS_THRESHOLD = 60

# 실제 기능이 작동하는 기준
ACTION_TRIGGER_THRESHOLD = 61

# 눈 감김이 지속된 프레임 수 저장
closed_frames = 0

# 상태 제어 변수
action_done = False
sleep_report_sent = False
media_paused_by_system = False
sleep_session_active = False

# Face Mesh 모델 생성
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)


# =========================
# EAR Calculation Functions
# =========================
def calculate_distance(point1, point2):
    return np.linalg.norm(point1 - point2)


def calculate_ear(eye_points):
    p1, p2, p3, p4, p5, p6 = eye_points

    vertical_1 = calculate_distance(p2, p6)
    vertical_2 = calculate_distance(p3, p5)
    horizontal = calculate_distance(p1, p4)

    ear = (vertical_1 + vertical_2) / (2.0 * horizontal)
    return ear


def get_eye_points(face_landmarks, eye_indices, frame_width, frame_height):
    eye_points = []

    for index in eye_indices:
        landmark = face_landmarks.landmark[index]

        x = int(landmark.x * frame_width)
        y = int(landmark.y * frame_height)

        eye_points.append(np.array([x, y]))

    return np.array(eye_points)


# =========================
# Camera Start
# =========================
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Failed to open camera")
    exit()

while True:
    ret, frame = cap.read()

    if not ret:
        print("Failed to read camera frame")
        break

    frame = cv2.flip(frame, 1)

    frame_height, frame_width, _ = frame.shape

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb_frame.flags.writeable = False

    results = face_mesh.process(rgb_frame)

    rgb_frame.flags.writeable = True

    status = "NO FACE"
    avg_ear = 0.0

    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:

            mp_drawing.draw_landmarks(
                image=frame,
                landmark_list=face_landmarks,
                connections=mp_face_mesh.FACEMESH_CONTOURS,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_contours_style()
            )

            left_eye_points = get_eye_points(
                face_landmarks,
                LEFT_EYE,
                frame_width,
                frame_height
            )

            right_eye_points = get_eye_points(
                face_landmarks,
                RIGHT_EYE,
                frame_width,
                frame_height
            )

            left_ear = calculate_ear(left_eye_points)
            right_ear = calculate_ear(right_eye_points)

            avg_ear = (left_ear + right_ear) / 2.0

            # =========================
            # Status Decision
            # =========================
            if avg_ear < EAR_THRESHOLD:
                closed_frames += 1
            else:
                closed_frames = 0

            # 60프레임부터 화면에는 DROWSY 표시
            if closed_frames >= DROWSY_STATUS_THRESHOLD:
                status = "DROWSY"
            elif closed_frames > 0:
                status = "EYES CLOSED"
            else:
                status = "AWAKE"

            # =========================
            # Mode-based Action Control
            # 1~59: EYES CLOSED, 기능 X
            # 60: DROWSY 표시
            # 61 이상: 실제 기능 작동
            # =========================
            if closed_frames >= ACTION_TRIGGER_THRESHOLD and not action_done:

                print(
                    f"DEBUG ACTION TRIGGERED: "
                    f"status={status}, closed_frames={closed_frames}, "
                    f"action_threshold={ACTION_TRIGGER_THRESHOLD}"
                )

                if MODE == "wake":
                    # Wake-Up Mode:
                    # 램프 ON 유지, 부저 울림, 영상 정지
                    send_request("wake_drowsy")
                    pause_youtube()
                    media_paused_by_system = True

                    print("Wake-Up Mode action executed")

                elif MODE == "sleep":
                    # Sleep-Aid Mode:
                    # 졸음 시작 = 수면 시작
                    # 램프 OFF, 부저 X, 영상 정지, 수면 시작 기록
                    send_request("sleep_start")
                    pause_youtube()
                    media_paused_by_system = True

                    sleep_session_active = True
                    sleep_report_sent = False

                    print("Sleep-Aid Mode action executed")

                action_done = True

            # =========================
            # AWAKE 처리
            # 깨우기 모드: 영상 다시 재생
            # 재우기 모드: 수면 종료 리포트 메일 전송
            # =========================
            if status == "AWAKE":

                if MODE == "wake":
                    if action_done and media_paused_by_system:
                        play_youtube()
                        media_paused_by_system = False
                        print("Wake-Up Mode: user awake, media resumed")

                    action_done = False

                elif MODE == "sleep":
                    if sleep_session_active and not sleep_report_sent:
                        send_request("sleep_end")
                        sleep_report_sent = True
                        sleep_session_active = False
                        print("Sleep-Aid Mode: user awake, sleep report sent")

                    action_done = False

            # 눈 포인트 표시
            for point in left_eye_points:
                cv2.circle(frame, tuple(point), 2, (0, 255, 0), -1)

            for point in right_eye_points:
                cv2.circle(frame, tuple(point), 2, (0, 255, 0), -1)

    else:
        # 얼굴이 감지되지 않으면 closed_frames만 초기화
        # 수면 세션 종료 처리는 AWAKE 상태에서만 처리
        closed_frames = 0
        status = "NO FACE"

    # =========================
    # Display Info
    # =========================
    cv2.putText(
        frame,
        f"Mode: {MODE}",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 0),
        2
    )

    cv2.putText(
        frame,
        f"EAR: {avg_ear:.2f}",
        (30, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2
    )

    cv2.putText(
        frame,
        f"Status: {status}",
        (30, 120),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 0, 255),
        2
    )

    cv2.putText(
        frame,
        f"Closed Frames: {closed_frames}",
        (30, 160),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2
    )

    cv2.imshow("Sleep Detection Test", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


# =========================
# Cleanup
# =========================
cap.release()
face_mesh.close()
cv2.destroyAllWindows()