import cv2
import streamlit as st
import numpy as np
import tempfile
from run_test_models import draw
import project_utilities as pu
import mediapipe as mp


st.title("Crux Cam")
uploaded_file = st.file_uploader("Choose a file", type=['mp4', 'mov'])

if uploaded_file is None:
    st.write("Upload a video file")
    
else:
    tfile = tempfile.NamedTemporaryFile(delete=False)
    tfile.write(uploaded_file.read())
    cap = cv2.VideoCapture(tfile.name)
    
    frame_placeholder = st.empty()

    mpPose = mp.solutions.pose
    mpDraw = mp.solutions.drawing_utils
            
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    pTime = 0
    min_angle = float('-inf')
    angle_threshold = 90
    good_frames = 0
    bad_frames = 0
    font = cv2.FONT_HERSHEY_SIMPLEX
    blue = (255, 127, 0)
    red = (50, 50, 255)
    green = (127, 255, 0)
    dark_blue = (127, 20, 0)
    light_green = (127, 233, 100)
    yellow = (0, 255, 255)
    pink = (255, 0, 255)
    black = (0, 0, 0)
    

    # fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    # out = cv2.VideoWriter(pu.output_path, fourcc, fps, (width, height)) 
    pose = pu.mpPose.Pose()
    stop_button = st.button("Stop")

    while cap.isOpened() and not stop_button:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(frame)
        
        
        if results.pose_landmarks:
            h, w, c = frame.shape
            
            landmarks = results.pose_landmarks.landmark
            
            r_shoulder, r_elbow, r_wrist = pu.r_arm_landmarks(landmarks, h, w, c)
            l_shoulder, l_elbow, l_wrist = pu.l_arm_landmarks(landmarks, h, w, c)

            r_bicep_angle = pu.angle_between(r_shoulder[0] - r_elbow[0], r_shoulder[1] - r_elbow[1], 
                                        r_wrist[0] - r_elbow[0], r_wrist[1] - r_elbow[1])
            l_bicep_angle = pu.angle_between(l_shoulder[0] - l_elbow[0], l_shoulder[1] - l_elbow[1], 
                                        l_wrist[0] - l_elbow[0], l_wrist[1] - l_elbow[1])

            bad_frames, good_frames = pu.draw_landmarks_by_angle(frame, results, r_bicep_angle, l_bicep_angle, angle_threshold, bad_frames, good_frames)

            frac_good = good_frames / (good_frames + bad_frames)

        frame_placeholder.image(frame, channels='RGB')   
        if cv2.waitKey(1) & 0xFF == ord('q') or stop_button:
            break
    
    efficiency, good, bad = st.columns(3)
    efficiency.metric(label="Efficiency", value =f"{round(frac_good * 100.0, 2)}/100")
    good.metric(label="Good Frames: ", value= good_frames)
    bad.metric(label="Bad Frames: ", value= bad_frames)
    
    cap.release()
    # out.release()
    cv2.destroyAllWindows()