import cv2
import time
import math
import numpy as np
import mediapipe as mp

# Following https://learnopencv.com/building-a-body-posture-analysis-system-using-mediapipe/
mpPose = mp.solutions.pose
mpDraw = mp.solutions.drawing_utils
font = cv2.FONT_HERSHEY_SIMPLEX
blue = (255, 127, 0)
red = (50, 50, 255)
green = (127, 255, 0)
dark_blue = (127, 20, 0)
light_green = (127, 233, 100)
yellow = (0, 255, 255)
pink = (255, 0, 255)
black = (0, 0, 0)
        
def r_arm_landmarks(landmarks, h, w, c):
    r_shoulder = (landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].x * w, 
                landmarks[mpPose.PoseLandmark.RIGHT_SHOULDER.value].y * h)
    r_elbow = (landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].x * w, 
            landmarks[mpPose.PoseLandmark.RIGHT_ELBOW.value].y * h)
    r_wrist = (landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].x * w, 
            landmarks[mpPose.PoseLandmark.RIGHT_WRIST.value].y * h)
            
    return r_shoulder, r_elbow, r_wrist


def l_arm_landmarks(landmarks, h, w, c):
    l_shoulder = (landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].x * w, 
                landmarks[mpPose.PoseLandmark.LEFT_SHOULDER.value].y * h)
    l_elbow = (landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].x * w, 
            landmarks[mpPose.PoseLandmark.LEFT_ELBOW.value].y * h)
    l_wrist = (landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].x * w, 
            landmarks[mpPose.PoseLandmark.LEFT_WRIST.value].y * h)
    
    return l_shoulder, l_elbow, l_wrist


def draw_landmarks_by_angle(img, results, r_bicep_angle, l_bicep_angle, angle_threshold, bad_frames, good_frames):
    if r_bicep_angle <= angle_threshold and l_bicep_angle <= angle_threshold:
                bad_frames += 1
                mpDraw.draw_landmarks(img, 
                                results.pose_landmarks, 
                                mpPose.POSE_CONNECTIONS, 
                                mpDraw.DrawingSpec(color=blue, thickness=2, circle_radius=2),
                                mpDraw.DrawingSpec(color=red, thickness=2, circle_radius=2)
                                )
    else:
        good_frames += 1
        mpDraw.draw_landmarks(img, 
                        results.pose_landmarks, 
                        mpPose.POSE_CONNECTIONS, 
                        mpDraw.DrawingSpec(color=blue, thickness=2, circle_radius=2),
                        mpDraw.DrawingSpec(color=green, thickness=2, circle_radius=2)
                        )
        
    return bad_frames, good_frames
    
def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """
    uses the euclidean distance formula to calculate the distance b/w two points (x1, y1) and (x2, y2)
    
    Args:
        x1 (float): x-value of point 1
        y1 (float): y-value of point 1
        x2 (float): x-value of point 2
        y2 (float): y-value of point 2

    Returns:
        float: distance between two points
    """
    dist = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    return dist


def angle_between(x1: float, y1: float, x2: float, y2: float) -> float:
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


def put_text_with_background(image, text, position, font, scale, color, thickness, bg_color):
    (text_width, text_height), baseline = cv2.getTextSize(text, font, scale, thickness)
    bottom_left = (position[0], position[1] + baseline)
    top_right = (position[0] + text_width, position[1] - text_height - baseline)
    cv2.rectangle(image, bottom_left, top_right, bg_color, cv2.FILLED)
    cv2.putText(image, text, position, font, scale, color, thickness)