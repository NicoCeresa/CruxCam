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