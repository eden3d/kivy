"""
Camera
======

Core class for acquiring the camera and converting its input into a
:class:`~kivy.graphics.texture.Texture`.

.. versionchanged:: 1.8.0
    There is now 2 distinct Gstreamer implementation: one using Gi/Gst
    working for both Python 2+3 with Gstreamer 1.0, and one using PyGST
    working only for Python 2 + Gstreamer 0.10.
    If you have issue with GStreamer, have a look at
    :ref:`gstreamer-compatibility`

.. versionchanged:: 1.9.0
    The Gi implementation has been disabled, meaning that there is no working
    implementation for Python 3.

.. versionchanged:: 1.9.1
    The CameraBase abstract class has been rewritten from scratch, while
    maintaining retro compatibility. The providers handling code has been
    rewritten, but keeping the exact same logic.

"""
#
# TODO: Implement retro-compatibility (with 1.9.0's CameraBase class)
#
from sys import version_info
from abc import ABCMeta, abstractmethod

from kivy.utils import platform
from kivy.event import EventDispatcher
from kivy.logger import Logger
from kivy.core import core_select_lib

DEFAULT_INDEX = 0
DEFAULT_RESOLUTION = 640, 480

_VIDEOCAPTURE = 'videocapture', 'camera_videocapture', 'CameraVideoCapture'
_AVFOUNDATION = 'avfoundation', 'camera_avfoundation', 'CameraAVFoundation'
_ANDROID = 'android', 'camera_android', 'CameraAndroid'
_PYGST = 'pygst', 'camera_pygst', 'CameraPyGst'
_GI = 'gi', 'camera_gi', 'CameraGi'
_OPENCV2 = 'opencv', 'camera_opencv', 'CameraOpenCV'
_OPENCV3 = 'opencv3', 'camera_opencv3', 'CameraOpenCV'


__all__ = (
    'DEFAULT_INDEX', 'DEFAULT_RESOLUTION',
    'CameraBase', 'Camera'
)

"""
Camera base abstract class
++++++++++++++++++++++++++
"""


class CameraBase(EventDispatcher, metaclass=ABCMeta):
    """Abstract color camera widget

    .. warning:: Concrete camera classes must implement the following 6
                 abstract methods :
                  - device grabbing (:func:`open`, :func:`close`)
                  - camera configuration (:func:`configure`)
                  - capture scheduling (:func:`start`, :func:`stop`)
                  - sending captured frame to GPU (:func:`paint`)

    :Parameters:
        `index`: int
            Source index of the camera.
        `resolution` : tuple (int, int)
            Resolution to try to request from the camera.
            Used in the gstreamer pipeline by forcing the appsink caps
            to this resolution. If the camera doesnt support the resolution,
            a negotiation error might be thrown.
        `size` : tuple (int, int)
            Size at which the image is drawn. If no size is specified,
            it defaults to the resolution of the camera image.

    :Events:
        `on_load`
            Fired when the camera is loaded and the texture has become
            available.
        `on_frame`
            Fired each time the camera texture is updated.

    Class attributes
    ----------------
    """
    image_format = 'rgb'
    __events__ = ('on_load', 'on_texture')

    """
    Initializer & events handlers
    -----------------------------
    """
    def __init__(self, **kwargs):
        self._index = kwargs.get('index', DEFAULT_INDEX)
        self._resolution = kwargs.get('resolution', DEFAULT_RESOLUTION)
        kwargs.setdefault('size', self._resolution)

        self._buffer = None
        self._texture = None
        self._device = None

        self._acquired = False
        self._configured = False
        self._started = False

        super(CameraBase, self).__init__(**kwargs)

        if not kwargs.get('stopped', self.default_stopped):
            self.start()

    def on_texture(self):
        pass

    def on_load(self):
        pass

    """
    Camera read-only properties
    ---------------------------
    """
    @property
    def acquired(self):
        return self._acquired

    @property
    def configured(self):
        return self._configured

    @property
    def started(self):
        return self._started

    @property
    def fps(self):
        return self._fps

    @property
    def interval(self):
        return 1 / float(self.fps)

    """
    Camera writable properties
    --------------------------
    (these properties trigger reconfiguration when their value is modified)
    """
    @property
    def resolution(self):
        return self._resolution

    @resolution.setter
    def resolution(self, value):
        if value != self._resolution:
            self._resolution = value
            self.configure()

    @property
    def index(self):
        return self._index

    @index.setter
    def index(self, value):
        if value != self._index:
            self._index = value
            self.close()
            self.open()

    """
    Paint method - should be called by the update() implementation
    --------------------------------------------------------------
    """
    def paint(self, buffer):
        """Copy the the buffer into the texture"""
        texture = self._texture

        if texture is None:
            Logger.warning(
                "Could not paint image buffer, texture is undefined"
            )
        else:
            texture.blit_buffer(buffer, colorfmt=image_format)

        self.dispatch('on_texture')

    """
    Abstract methods
    ----------------
     - All of these methods should be implemented by Camera providers
     - All implementations should call their super-method before actually doing
    the implemented operation
    """
    @abstractmethod
    def open(self):
        """Initialize capture device and acquire camera

        """
        self._acquired = True

    @abstractmethod
    def close(self):
        """Release camera and close capture device"

        """
        if self.started:
            self.stop()
        self._acquired = False

    @abstractmethod
    def configure(self):
        """Configure capture device

        (usually, setting the resolution and correcting our resolution with the
        resolution of the received frame, as some cameras may not obey.)

        """
        if not self.acquired:
            self.open()
        self._configured = True

    @abstractmethod
    def start(self):
        """Start frame acquisition

        The implementation of this abstract method should schedule the next
        frame updates using the FPS obtained at the configuration step.

        """
        if not self.configured:
            self.configure()
        self._started = True

    @abstractmethod
    def stop(self):
        """Stop frame acquisition.

        The implementation of this abstract method should unschedule the frame
        updates (but not release the camera, see :func:`close`).

        """
        self._started = False

    @abstractmethod
    def update(self, delta):
        """Update the current frame with camera's data (internal).

        .. note:: The implementation of this abstract method should be calling
        :func:`paint` when it has a read an image buffer from the camera.

        """
        pass

    """
    Context manager
    ---------------
    (allows the Camera object to be used as a context descriptor)
    """
    def __enter__(self):
        """Enter the camera context (opens camera & starts capture)"""
        self.start()
        return self

    def __exit__(self, *exc_details):
        """Exit the camera context (stops capture & closes camera)"""
        self.close()


"""
Camera provider handling
++++++++++++++++++++++++
"""
def _compatible_providers(platform, python_version):
    if platform == 'win':
        yield _VIDEOCAPTURE
    elif platform == 'macosx':
        yield _AVFOUNDATION)
    elif platform == 'android':
        yield _ANDROID)
    else:
        # yield _GI
        # FIXME: Why is Gi disabled ?
        yield _PYGST

    yield _OPENCV3

    if python_version.major == 2:
        yield _OPENCV2


Camera = core_select_lib(
    'camera',
    _compatible_providers(platform, version_info)
)
