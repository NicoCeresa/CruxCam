import os
import sys
sys.path.insert(0, 'G:/Projects/CruxCam/notebooks')
import cv2
import time
import math
import numpy as np
import mediapipe as mp
from pathlib import Path
import project_utilities as pu

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


class draw:
    def __init__(self, input_path, output_path):
        self.input_path = input_path
        self.output_path = output_path
        self.mpPose = mp.solutions.pose
        self.mpDraw = mp.solutions.drawing_utils
        
    def r_arm_landmarks(self, landmarks, h, w, c):

        r_shoulder = (landmarks[self.mpPose.PoseLandmark.RIGHT_SHOULDER.value].x * w, 
                    landmarks[self.mpPose.PoseLandmark.RIGHT_SHOULDER.value].y * h)
        r_elbow = (landmarks[self.mpPose.PoseLandmark.RIGHT_ELBOW.value].x * w, 
                landmarks[self.mpPose.PoseLandmark.RIGHT_ELBOW.value].y * h)
        r_wrist = (landmarks[self.mpPose.PoseLandmark.RIGHT_WRIST.value].x * w, 
                landmarks[self.mpPose.PoseLandmark.RIGHT_WRIST.value].y * h)
                
        return r_shoulder, r_elbow, r_wrist


    def l_arm_landmarks(self, landmarks, h, w, c):
        l_shoulder = (landmarks[self.mpPose.PoseLandmark.LEFT_SHOULDER.value].x * w, 
                    landmarks[self.mpPose.PoseLandmark.LEFT_SHOULDER.value].y * h)
        l_elbow = (landmarks[self.mpPose.PoseLandmark.LEFT_ELBOW.value].x * w, 
                landmarks[self.mpPose.PoseLandmark.LEFT_ELBOW.value].y * h)
        l_wrist = (landmarks[self.mpPose.PoseLandmark.LEFT_WRIST.value].x * w, 
                landmarks[self.mpPose.PoseLandmark.LEFT_WRIST.value].y * h)
        
        return l_shoulder, l_elbow, l_wrist


    def draw_landmarks_by_angle(self, img, results, r_bicep_angle, l_bicep_angle, angle_threshold, bad_frames, good_frames):
        if r_bicep_angle <= angle_threshold and l_bicep_angle <= angle_threshold:
                    bad_frames += 1
                    self.mpDraw.draw_landmarks(img, 
                                    results.pose_landmarks, 
                                    self.mpPose.POSE_CONNECTIONS, 
                                    self.mpDraw.DrawingSpec(color=yellow, thickness=2, circle_radius=2),
                                   self.mpDraw.DrawingSpec(color=red, thickness=2, circle_radius=2))
        else:
            good_frames += 1
            self.mpDraw.draw_landmarks(img, 
                            results.pose_landmarks, 
                            self.mpPose.POSE_CONNECTIONS, 
                            self.mpDraw.DrawingSpec(color=yellow, thickness=2, circle_radius=2),
                            self.mpDraw.DrawingSpec(color=green, thickness=2, circle_radius=2))
            
        return bad_frames, good_frames
    
    def put_text_with_background(self, image, text, position, font, scale, color, thickness, bg_color):
        (text_width, text_height), baseline = cv2.getTextSize(text, font, scale, thickness)
        bottom_left = (position[0], position[1] + baseline)
        top_right = (position[0] + text_width, position[1] - text_height - baseline)
        cv2.rectangle(image, bottom_left, top_right, bg_color, cv2.FILLED)
        cv2.putText(image, text, position, font, scale, color, thickness)
            
    def angle_between(self, x1: float, y1: float, x2: float, y2: float) -> float:
        """
        calculates the inner angle between two vectors: P_12 and P_13

        Args:
            x1 (float): x-value of point 1
            y1 (float): y-value of point 1
            x2 (float): x-value of point 2
            y2 (float): y-value of point 2

        Returns:
            float: theta in degrees
        """
        vec1 = np.array([x1, y1])
        vec2 = np.array([x2, y2])
        
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        cos_theta = np.dot(vec1, vec2) / (norm1 * norm2)
        cos_theta = np.clip(cos_theta, -1.0, 1.0)
        
        theta_rads = np.arccos(cos_theta)
        theta_deg = np.degrees(theta_rads)
        
        return theta_deg

    def display_pose_detection(self):
        assert Path(self.input_path).exists
        
        cap = cv2.VideoCapture(self.input_path)
        if not cap.isOpened():
            print("Error: Could not open video file.")
            exit()
        
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        pTime = 0
        min_angle = float('-inf')
        angle_threshold = 90
        good_frames = 0
        bad_frames = 0

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(self.output_path, fourcc, fps, (width, height)) 
        pose = self.mpPose.Pose()

        while True:
            success, img = cap.read()
            if not success:
                break

            imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = pose.process(imgRGB)
            
            if results.pose_landmarks:
                h, w, c = img.shape
                
                landmarks = results.pose_landmarks.landmark
                
                r_shoulder, r_elbow, r_wrist = self.r_arm_landmarks(landmarks, h, w, c)
                l_shoulder, l_elbow, l_wrist = self.l_arm_landmarks(landmarks, h, w, c)

                r_bicep_angle = self.angle_between(r_shoulder[0] - r_elbow[0], r_shoulder[1] - r_elbow[1], 
                                            r_wrist[0] - r_elbow[0], r_wrist[1] - r_elbow[1])
                l_bicep_angle = self.angle_between(l_shoulder[0] - l_elbow[0], l_shoulder[1] - l_elbow[1], 
                                            l_wrist[0] - l_elbow[0], l_wrist[1] - l_elbow[1])

                bad_frames, good_frames = self.draw_landmarks_by_angle(img, results, r_bicep_angle, l_bicep_angle, angle_threshold, bad_frames, good_frames)

                frac_good = good_frames / (good_frames + bad_frames)

                self.put_text_with_background(image=img, 
                                        text=f"Climbing Efficiency: {(frac_good * 100.0):.2f}", 
                                        position=(10, 45), 
                                        font=cv2.FONT_HERSHEY_SIMPLEX, 
                                        scale=1, 
                                        color=blue, 
                                        thickness=1, 
                                        bg_color=black)
                self.put_text_with_background(image=img, 
                                        text=f"Good: {good_frames}", 
                                        position=(10,70), 
                                        font=font, 
                                        scale=.5, 
                                        color=green, 
                                        thickness=1, 
                                        bg_color=black)
                self.put_text_with_background(image=img,
                                        text=f"Bad: {bad_frames}",
                                        position=(10,100), 
                                        font=font, 
                                        scale=.5, 
                                        color=red, 
                                        thickness=1,
                                        bg_color=black)
                
            out.write(img)
            cv2.imshow("Image", img)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
        print(f"Bad Frames: {bad_frames}\nGood Frames: {good_frames}")
        cap.release()
        out.release()
        cv2.destroyAllWindows()
        return bad_frames, good_frames

if __name__ == '__main__':
    input_path = 'inputs/tomoa_outside.mp4'
    output_path = 'outputs/output_video2.mp4'
    (draw(input_path=input_path,
         output_path=output_path)
    .display_pose_detection())