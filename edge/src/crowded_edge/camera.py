from __future__ import annotations

from crowded_edge.settings import DeviceSettings


class Camera:
    def __init__(self, settings: DeviceSettings) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("OpenCV is not installed") from exc
        self._cv2 = cv2
        self._jpeg_quality = settings.jpeg_quality
        self._capture = cv2.VideoCapture(settings.camera_device)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, settings.width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.height)
        if not self._capture.isOpened():
            raise RuntimeError(f"cannot open camera device {settings.camera_device}")

    def capture_jpeg(self) -> bytes:
        ok, frame = self._capture.read()
        if not ok:
            raise RuntimeError("camera frame capture failed")
        ok, encoded = self._cv2.imencode(
            ".jpg",
            frame,
            [self._cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality],
        )
        if not ok:
            raise RuntimeError("JPEG encoding failed")
        return encoded.tobytes()

    def close(self) -> None:
        self._capture.release()

    def __enter__(self) -> "Camera":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

