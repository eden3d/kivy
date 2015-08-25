"""
OpenCV Camera: Implement CameraBase with OpenCV (cv2 module)

Author: Hugo Geoffroy "pistache" <h.geoffroy@eden-3d.org>

"""
# Tasks
# ----
# - TODO: use threads or multiprocessing instead of rescheduling


# Imports
# -------
from kivy.logger import Logger
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.core.camera import CameraBase

from cv2 import (
    VideoCapture,
    CAP_PROP_FRAME_WIDTH as FRAME_WIDTH,
    CAP_PROP_FRAME_HEIGHT as FRAME_HEIGHT,
    CAP_PROP_FPS as FPS,
)

# Constants
# ---------
IMAGE_FORMAT = 'bgr'  # OpenCV image format
FALLBACK_FPS = 30

# Exports
# -------
__all__ = ['IMAGE_FORMAT', 'CaptureError', 'CameraOpenCV', ]


# Exception classes
# -----------------
class CaptureError(RuntimeError):
    """Raised by the Camera methods & scheduled routines. Should be catched and
    translated to a proper kivy logged exception, if it's possible to recover
    and continue.

    """
    def __init__(self, message, camera):
        """Initialize capture error exception. Store the camera as exception
        attributes.

        """
        self.camera = camera

        super().__init__(message)


# Camera provider class
# ---------------------
class CameraOpenCV(CameraBase):
    """Implementation of CameraBase using OpenCV

    Uses the :mod:`cv2` module, and its :class:`cv2.VideoCapture` class.

    """

    def __init__(self, **kwargs):
        """Initialize OpenCV Camera provider"""
        self.capture = VideoCapture()

        if __debug__:
            Logger.debug(
                "Camera: initializing capture ({})'"
                "".format(self.capture)
            )

        try:
            super(CameraOpenCV, self).__init__(**kwargs)
        except CaptureError as ex:
            Logger.exception(
                "Camera: Exception while initializing camera : {}"
                "".format(ex)
            )

    def _configure_fps(self):
        fps = self.capture.get(FPS)

        if fps <= 0:
            Logger.info(
                "invalid FPS ('{}') returned by camera, using {} as fallback"
                "".format(self.fps, FALLBACK_FPS)
            )
            self._fps = FALLBACK_FPS
        elif self._fps != fps:
            self._fps = fps

    def _configure_resolution(self):
        width, height = self._resolution

        self.capture.set(FRAME_WIDTH, width)
        self.capture.set(FRAME_HEIGHT, height)

        ok, frame = self.capture.read()

        if not ok:
            raise CaptureError("could not read initial image", self)

        frame_height = len(frame)
        frame_width = len(frame[0])

        if width != frame_width or height != frame_height:
            Logger.info(
                "Camera: size corrected by camera : {}x{}"
                "".format(frame_width, frame_height)
            )
            # NOTE: do not use property here, it would cause infinite
            # recursion. We want to update the resolution with the frame's size
            # without triggering resolution reconfiguration
            self._resolution = frame_width, frame_height

    def _create_texture(self):
        self._texture = Texture.create(self._resolution)
        self._texture.flip_vertical()

        self.dispatch('on_load')

    def open(self):
        super().open()

        self.capture.open(self.index)

    def close(self):
        super().stop()

        self.capture.release()

    def configure(self):
        super().configure()

        self._configure_resolution()
        self._configure_fps()

    def start(self):
        """Start frame updating.

        This method is not blocking, the update routine is just scheduled in
        Kivy's clock."""
        super(CameraOpenCV, self).start()

        if not self.capture.isOpened():
            raise CaptureError("Camera is not open")

        self.unschedule()
        Clock.schedule(self.update, self.interval)

    def stop(self):
        """Stop frame updating. This does not release the camera.

        This method is not blocking, the update routine is just unscheduled
        from Kivy's clock.

        """
        super(CameraOpenCV, self).stop()

        Clock.unschedule(self.update)

        if __debug__:
            Logger.debug("Camera: capture stopped")

    def update(self, delta):
        """Update GPU buffer with camera image data.

        """
        super().update()

        if self.stopped:
            # Don't update it camere stopped
            Logger.info("Camera: frame update skipped as camera is stopped")
            return

        if self._texture is None:
            self._create_texture()

        ok, frame = self.capture.read()

        if not ok:
            raise CaptureError("Could not read image from camera", self)

        self.paint(frame.tostring())
