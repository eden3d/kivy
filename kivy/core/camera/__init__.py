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
#  - init_camera() : should be OK
#
from sys import version_info
from abc import ABCMeta, abstractmethod

from kivy.core import core_select_lib
from kivy.utils import platform

from kivy.event import EventDispatcher
from kivy.clock import Clock
from kivy.logger import Logger

from kivy.graphics.texture import Texture

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

    def __init__(self, **kwargs):
        """Camera base class initializer"""
        self._index = kwargs.get('index', DEFAULT_INDEX)
        self._resolution = kwargs.get('resolution', DEFAULT_RESOLUTION)

        self._buffer = None
        self._texture = None

        self._acquired = False
        self._ready = False
        self._started = False

        self._clock = Clock()
        self._fps = 0

        super(CameraBase, self).__init__()

        if not kwargs.get('stopped', False):
            self.start()

    def on_texture(self):
        pass

    def on_load(self):
        pass

    """Camera read-only properties
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    The value of these properties is read-only and should normally not be
    modified by users of this class or subclasses, as it should be set
    exclusively by internal methods defined in this base class.

    """
    @property
    def acquired(self):
        return self._acquired

    @property
    def ready(self):
        return self._ready

    @property
    def started(self):
        return self._started

    @property
    def stopped(self):
        return not self._started

    """Computed properties
    ~~~~~~~~~~~~~~~~~~~~~~

    These properties values are either computed from other properties, or their
    value is automatically initialized by their getter when it is not set

    """
    @property
    def interval(self):
        return 1 / float(self.fps)

    @property
    def texture(self):
        if self._texture is None:
            self._texture = Texture.create(self._resolution)
            self._texture.flip_vertical()
            self.dispatch('on_load')
        return self._texture

    """Camera writable properties
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    These properties trigger events when their values are modified

    """

    # Index and resolution properties (they trigger reconfiguration when
    # changed, if a camera is acquired)
    @property
    def resolution(self):
        return self._resolution

    @resolution.setter
    def resolution(self, value):
        if value != self._resolution:
            self._resolution = value
            if self.acquired and self.ready:
                self.prepare()

    @property
    def index(self):
        return self._index

    @index.setter
    def index(self, value):
        if value != self._index:
            self._index = value
            if self.acquired:
                self.acquire()

    # FPS property (triggers rescheduling on update, if started)
    @property
    def fps(self):
        return self._fps

    @fps.setter
    def fps(self, value):
        if value != self._fps:
            self._fps = value
            if self.started:
                self.schedule()

    """Frame updating methods
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    These methods handle updating the texture with the image buffer using the
    correct color format, by scheduling them with Kivy's `Clock`.
    """
    def unschedule(self):
        self.clock.unschedule(self.update)

    def schedule(self):
        self.unschedule()
        self.clock.schedule(self.update, self.interval)

    def update(self, buffer):
        self.texture._blit_buffer(buffer, colorfmt=self.image_format)

    """Camera handling methods
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    These methods handle camera acquisition, preparation and release.

    These methods are public methods, and should do their best not to raise an
    exception, for example by stopping the capture before releasing the camera.

    """
    def acquire(self):
        if self.acquired:
            Logger.info(
                "Camera: asked to acquire camera while already open, "
                "closing beforehand"
            )
            self.release()
        self.open()
        self._acquired = True
        self._ready = False

    def release(self):
        if self.started:
            self.stop()
        self.close()
        self._acquired = False

    def prepare(self):
        self._ready = False
        if not self.acquired:
            self._acquire()
        self.configure()
        self._ready = True

    """Image capture control methods
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    These methods start and stop the camera feedback, by scheduling and
    unscheduling the frame update routine.

    """
    def start(self):
        if not self.ready:
            self.prepare()
        self.schedule()
        self._started = True

    def stop(self):
        self.unschedule()
        self._started = False

    """Abstract methods
    ~~~~~~~~~~~~~~~~~~~

    These methods should be implemented by the Camera providers as
    methods. These methods should be as idempotent as possible, the only expected
    side-effects are the FPS and resolution changes in :func:`configure`.

    """
    @abstractmethod
    def open(self):
        """Initialize capture device and acquire camera.

        """
        pass

    @abstractmethod
    def close(self):
        """Release camera and close capture device.

        """
        pass

    @abstractmethod
    def configure(self):
        """Configure capture device.

        Usually, set the resolution and correct our resolution with the
        resolution of the received frame, as some cameras may not obey.

        """
        pass

    @abstractmethod
    def read(self):
        """Read image from camera and return as string buffer.

        """
        pass

    """Context manager
    ~~~~~~~~~~~~~~~~~~

    Allows the Camera object to be used as a context descriptor.

    """
    def __enter__(self):
        """Enter the camera context (opens camera & starts capture)"""
        self.start()
        return self

    def __exit__(self, *exc_details):
        """Exit the camera context (stops capture & closes camera)"""
        self.close()
        return False

    """Retro-compatibility methods
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Implemented to support the camera providers made for the old CameraBase
    class.

    """
    def init_camera(self):
        self.open()
        self.configure()

"""
Camera provider handling
++++++++++++++++++++++++
"""


def _compatible_providers(platform, python_version):
    if platform == 'win':
        yield _VIDEOCAPTURE
    elif platform == 'macosx':
        yield _AVFOUNDATION
    elif platform == 'android':
        yield _ANDROID
    else:
        # yield _GI
        # FIXME: Why is Gi disabled ?
        yield _PYGST

    yield _OPENCV3

    if python_version.major == 2:
        yield _OPENCV2


def _get_compatible_provider(platform, version_info):
    return core_select_lib(
        'camera',
        _compatible_providers(platform, version_info)
    )


Camera = _get_compatible_provider(platform, version_info)
