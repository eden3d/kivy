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
    image_format = 'bgr'
    initial_retry = 60
    fps_average_size = 5

    def __init__(self, **kwargs):
        """Initialize OpenCV Camera provider"""
        self.capture = VideoCapture()
        self._retry = self.initial_retry

        if __debug__:
            from collections import deque
            self._deltas = deque(maxlen=self.fps_average_size)
            Logger.debug(
                "Camera: initializing capture ({})'"
                "".format(self.capture)
            )

        super(CameraOpenCV, self).__init__(**kwargs)

    def _read_frame(self):
        try:
            ok, frame = self.capture.read()
        except OSError as ex:
            Logger.warning(
                "System exception while reading from camera : {}".format(ex)
            )
            ok, frame = False, None
        except MemoryError as ex:
            Logger.warning(
                "Memory exception while reading from camera : {}".format(ex)
            )
            ok, frame = False, None
        except Exception as ex:
            Logger.warning(
                "Unknown exception while reading from camera : {}".format(ex)
            )
        else:
            self.paint(frame.tostring())
        finally:
            if not ok:
                if self._retry:
                    Logger.warning("Could not read frame from camera, retrying...")
                    self._retry -= 1
                else:
                    Logger.exception(
                        "Failed getting image data from camera, "
                        "stopping capture..."
                    )
                    self.stop()

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

        frame = self._read_frame()
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

    def acquire(self):
        super().open()

        self.capture.open(self.index)

    def release(self):
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

        if self.capture.isOpened():
            Clock.unschedule(self.update)
            Clock.schedule_interval(self.update, self.interval)
        else:
            Logger.exception("Failed camera start, camera is not open")
            self.stop()

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
        super().update(delta)

        if __debug__:
            self._deltas.append(delta)
            avg_fps = 1 / (sum(self._deltas / len(self._deltas))
            Logger.debug(
                "Updating current camera frame "
                "(average FPS: {})".format(avg_fps)
            )

        if self.stopped:
            # Don't update it camere stopped
            Logger.info("Camera: frame update skipped as camera is stopped")
            return

        if self._texture is None:
            self._create_texture()

        self.paint(self._read_frame())
