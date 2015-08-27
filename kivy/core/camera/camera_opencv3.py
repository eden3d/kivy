"""
OpenCV Camera: Implement CameraBase with OpenCV (cv2 module)

Author: Hugo Geoffroy "pistache" <h.geoffroy@eden-3d.org>

"""
from kivy.core.camera import SimpleCameraBase
import cv2

__all__ = ['CameraOpenCV', ]


# Camera provider class
# ---------------------
class CameraOpenCV(SimpleCameraBase):
    """Implementation of CameraBase using OpenCV

    Uses the :mod:`cv2` module, and its :class:`cv2.VideoCapture` class.

    """
    image_format = 'bgr'

    # Initialization
    # ~~~~~~~~~~~~~~
    def __init__(self, **kwargs):
        """Initialize OpenCV Camera provider"""
        # not bound to any camera yet
        self.capture = cv2.VideoCapture()

        super(CameraOpenCV, self).__init__(**kwargs)

    # Camera configuration
    # ~~~~~~~~~~~~~~~~~~~~
    def set_device_resolution(self, width, height):
        """Set the camera's resolution"""
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def get_device_fps(self):
        """Get the capture FPS from the camera"""
        return self.capture.get(cv2.CAP_PROP_FPS)

    # Camera start/stop/read
    # ~~~~~~~~~~~~~~~~~~~~~~
    def open(self):
        """Open video capture file with given camera index"""
        self.capture.open(self.index)

    def close(self):
        """Close video capture"""
        self.capture.release()

    def read(self):
        """Read an image from the video capture stream"""
        ok, frame = self.capture.read()
        assert ok
        return frame
