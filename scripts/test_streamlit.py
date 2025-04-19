import cv2
import streamlit as st
import numpy as np
import tempfile
from run_test_models import draw
import project_utilities as pu
import mediapipe as mp

cap = cv2.VideoCapture(0)
st.title("Crux Cam")
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

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
# out = cv2.VideoWriter(pu.output_path, fourcc, fps, (width, height)) 
pose = pu.mpPose.Pose()
stop_button = st.button("Stop")

while cap.isOpened() and not stop_button:
    ret, frame = cap.read()
    if not ret:
        st.write("The video capture has ended")
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

        pu.put_text_with_background(image=frame, 
                                text=f"Climbing Efficiency: {(frac_good * 100.0):.2f}", 
                                position=(10, 45), 
                                font=cv2.FONT_HERSHEY_SIMPLEX, 
                                scale=1, 
                                color=blue, 
                                thickness=1, 
                                bg_color=black)
        pu.put_text_with_background(image=frame, 
                                text=f"Good: {good_frames}", 
                                position=(10,70), 
                                font=font, 
                                scale=.5, 
                                color=green, 
                                thickness=1, 
                                bg_color=black)
        pu.put_text_with_background(image=frame,
                                text=f"Bad: {bad_frames}",
                                position=(10,100), 
                                font=font, 
                                scale=.5, 
                                color=red, 
                                thickness=1,
                                bg_color=black)
    frame_placeholder.image(frame, channels='RGB')   
    # out.write(img)
    cv2.imshow("Image", frame)
    if cv2.waitKey(1) & 0xFF == ord('q') or stop_button:
        break
    
st.write(f"Bad Frames: {bad_frames}\nGood Frames: {good_frames}")
cap.release()
# out.release()
cv2.destroyAllWindows()