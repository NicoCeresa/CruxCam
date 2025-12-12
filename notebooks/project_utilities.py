import cv2
import time
import math
import numpy as np
import mediapipe as mp

# Following https://learnopencv.com/building-a-body-posture-analysis-system-using-mediapipe/

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