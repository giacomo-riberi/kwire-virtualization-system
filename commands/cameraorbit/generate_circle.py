import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def generate_circle(center, normal, radius, num_points=100):
    """
    Generate points on a circle in 3D space.

    Args:
    - center: The center of the circle as a numpy array of shape (3,).
    - normal: The normal vector of the plane containing the circle as a numpy array of shape (3,).
    - radius: The radius of the circle.
    - num_points: Number of points to generate on the circle.

    Returns:
    - points: A numpy array of shape (num_points, 3) containing the generated points.
    """
    # Normalize the normal vector
    normal = normal / np.linalg.norm(normal)

    # Generate an orthonormal basis for the plane containing the circle
    v1 = np.array([1.0, 0.0, 0.0], dtype=float)
    if np.allclose(v1, normal):
        v1 = np.array([0.0, 1.0, 0.0], dtype=float)
    v1 -= v1.dot(normal) * normal
    v1 /= np.linalg.norm(v1)
    v2 = np.cross(normal, v1)

    # Generate points on the circle using parametric equations
    theta = np.linspace(0, 2 * np.pi, num_points)
    points_on_plane = np.column_stack((np.cos(theta), np.sin(theta)))

    # Transform points to 3D
    points = center + radius * (np.outer(points_on_plane[:, 0], v1) + np.outer(points_on_plane[:, 1], v2))

    return points

# Define parameters
center = np.array([0.0, 0.0, 0.0], dtype=float)
normal = np.array([1.0, 1.0, 1.0], dtype=float)  # Circle lies in the YZ-plane
radius = 1.0

# Generate circle points
circle_points = generate_circle(center, normal, radius)

# Plot the circle
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')
ax.scatter(circle_points[:, 0], circle_points[:, 1], circle_points[:, 2])
ax.set_xlabel('X')
ax.set_ylabel('Y')
ax.set_zlabel('Z')
ax.set_title('Circle in 3D')
plt.show()
