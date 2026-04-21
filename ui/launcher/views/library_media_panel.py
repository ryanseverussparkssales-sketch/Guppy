from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSignalBlocker, Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
try:
    from PySide6.QtMultimediaWidgets import QVideoWidget
except ImportError:  # pragma: no cover - fallback for environments missing video widgets
    QVideoWidget = None
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.guppy.launcher_application.library_media import describe_library_media_path

from .. import tokens as T
from .library_view_components import body_label as _body
from .library_view_components import mono_label as _mono


class LibraryMediaPanel(QFrame):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        player_factory: Callable[[QWidget], object] | None = None,
        audio_output_factory: Callable[[QWidget], object] | None = None,
    ) -> None:
        super().__init__(parent)
        self._player_factory = player_factory or (lambda owner: QMediaPlayer(owner))
        self._audio_output_factory = audio_output_factory or (lambda owner: QAudioOutput(owner))
        self._player = None
        self._audio_output = None
        self._current_media_path = ""
        self._current_media_title = ""
        self._current_media_kind = ""

        self.setStyleSheet(
            "QFrame { background-color: rgba(255,255,255,0.62); border: 1px solid rgba(214,197,174,0.44); border-radius: 22px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(_mono("LOCAL MEDIA PLAYER", T.PRIMARY, T.FS_TINY, True))
        header.addStretch()
        self._unload_btn = QPushButton("UNLOAD")
        self._unload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._unload_btn.clicked.connect(self.unload_media)
        self._style_control_button(self._unload_btn)
        self._unload_btn.setEnabled(False)
        header.addWidget(self._unload_btn)
        layout.addLayout(header)

        self._hint_lbl = _body(
            "Load local audio or video from approved-root files or saved media artifacts. Playback stays inside Library.",
            color=T.DIM,
        )
        layout.addWidget(self._hint_lbl)

        self._current_title_lbl = _body("No media loaded yet.", color=T.INK, size=T.FS_LABEL)
        layout.addWidget(self._current_title_lbl)
        self._status_lbl = _body("Choose a media-capable Library item and click LOAD MEDIA.", color=T.DIM)
        layout.addWidget(self._status_lbl)

        surface = QFrame()
        surface.setStyleSheet(
            "QFrame { background-color: rgba(245,241,234,0.92); border: 1px solid rgba(214,197,174,0.40); border-radius: 18px; }"
        )
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(12, 12, 12, 12)
        surface_layout.setSpacing(8)
        self._video_widget = QVideoWidget(self) if QVideoWidget is not None else None
        if self._video_widget is not None:
            self._video_widget.setMinimumHeight(180)
            self._video_widget.hide()
            surface_layout.addWidget(self._video_widget)
        self._surface_placeholder = _body(
            "Video preview appears here when a local video is loaded. Audio playback keeps this panel as the control surface.",
            color=T.DIM,
        )
        surface_layout.addWidget(self._surface_placeholder)
        layout.addWidget(surface)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self._play_btn = QPushButton("PLAY")
        self._play_btn.clicked.connect(self._toggle_playback)
        self._stop_btn = QPushButton("STOP")
        self._stop_btn.clicked.connect(self.stop_media)
        for button in (self._play_btn, self._stop_btn):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._style_control_button(button)
            button.setEnabled(False)
            controls.addWidget(button)
        controls.addStretch()
        self._time_lbl = _mono("00:00 / 00:00", T.DIM, T.FS_TINY, True)
        controls.addWidget(self._time_lbl)
        layout.addLayout(controls)

        self._progress = QSlider(Qt.Orientation.Horizontal)
        self._progress.setRange(0, 0)
        self._progress.setEnabled(False)
        self._progress.sliderMoved.connect(self._seek_media)
        self._progress.setStyleSheet(
            f"QSlider::groove:horizontal {{ background: rgba(214,197,174,0.40); height: 4px; border-radius: 2px; }}"
            f"QSlider::handle:horizontal {{ background: {T.PRIMARY}; width: 14px; margin: -6px 0; border-radius: 7px; }}"
        )
        layout.addWidget(self._progress)

    @staticmethod
    def _style_control_button(button: QPushButton) -> None:
        button.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {T.PRIMARY}; border: 1px solid {T.BORDER};"
            f" border-radius: 12px; padding: 5px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.PRIMARY}; background: #ffffff; }}"
            f"QPushButton:disabled {{ color: {T.DIM}; border-color: rgba(214,197,174,0.30); background: rgba(255,255,255,0.75); }}"
        )

    def _ensure_player(self) -> None:
        if self._player is not None:
            return
        self._player = self._player_factory(self)
        self._audio_output = self._audio_output_factory(self)
        if hasattr(self._player, "setAudioOutput"):
            self._player.setAudioOutput(self._audio_output)
        if self._video_widget is not None and hasattr(self._player, "setVideoOutput"):
            self._player.setVideoOutput(self._video_widget)
        if hasattr(self._player, "playbackStateChanged"):
            self._player.playbackStateChanged.connect(self._sync_playback_state)
        if hasattr(self._player, "mediaStatusChanged"):
            self._player.mediaStatusChanged.connect(self._sync_media_status)
        if hasattr(self._player, "positionChanged"):
            self._player.positionChanged.connect(self._on_position_changed)
        if hasattr(self._player, "durationChanged"):
            self._player.durationChanged.connect(self._on_duration_changed)
        if hasattr(self._player, "errorOccurred"):
            self._player.errorOccurred.connect(self._handle_error)

    def load_media(self, title: str, item_path: str) -> bool:
        descriptor = describe_library_media_path(item_path)
        title_text = str(title or "").strip() or "Selected media"
        if not descriptor.is_media:
            self._set_status(f"Unsupported media file: {item_path or 'missing path'}", is_error=True)
            return False
        if not descriptor.exists:
            self._set_status(f"Media file not found: {descriptor.path or item_path}", is_error=True)
            return False
        self._ensure_player()
        self._current_media_title = title_text
        self._current_media_path = descriptor.path
        self._current_media_kind = descriptor.media_kind
        if hasattr(self._player, "setSource"):
            self._player.setSource(QUrl.fromLocalFile(descriptor.path))
        self._current_title_lbl.setText(title_text)
        self._set_status(f"Loaded local {descriptor.media_kind}: {title_text}", is_error=False)
        self._play_btn.setEnabled(True)
        self._stop_btn.setEnabled(True)
        self._unload_btn.setEnabled(True)
        self._progress.setEnabled(True)
        self._surface_placeholder.setText(
            "Video loaded. Use the controls below to pause, stop, or scrub playback."
            if descriptor.media_kind == "video"
            else "Audio loaded. Use the controls below to play, pause, stop, or scrub playback."
        )
        if self._video_widget is not None:
            self._video_widget.setVisible(descriptor.media_kind == "video")
        if hasattr(self._player, "play"):
            self._player.play()
        self._sync_playback_state()
        return True

    def stop_media(self) -> None:
        if self._player is None or not self._current_media_path:
            return
        if hasattr(self._player, "stop"):
            self._player.stop()
        self._set_status(f"Stopped media: {self._current_media_title}", is_error=False)
        self._sync_playback_state()

    def unload_media(self) -> None:
        if self._player is not None:
            if hasattr(self._player, "stop"):
                self._player.stop()
            if hasattr(self._player, "setSource"):
                self._player.setSource(QUrl())
        self._current_media_path = ""
        self._current_media_title = ""
        self._current_media_kind = ""
        self._current_title_lbl.setText("No media loaded yet.")
        self._set_status("Choose a media-capable Library item and click LOAD MEDIA.", is_error=False)
        self._play_btn.setText("PLAY")
        self._play_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)
        self._unload_btn.setEnabled(False)
        self._progress.setEnabled(False)
        with QSignalBlocker(self._progress):
            self._progress.setRange(0, 0)
            self._progress.setValue(0)
        self._time_lbl.setText("00:00 / 00:00")
        if self._video_widget is not None:
            self._video_widget.hide()
        self._surface_placeholder.setText(
            "Video preview appears here when a local video is loaded. Audio playback keeps this panel as the control surface."
        )

    def current_media_path(self) -> str:
        return self._current_media_path

    def current_media_title(self) -> str:
        return self._current_media_title

    def status_text(self) -> str:
        return self._status_lbl.text().strip()

    def _toggle_playback(self) -> None:
        if self._player is None or not self._current_media_path:
            return
        state = self._playback_state()
        if state == QMediaPlayer.PlaybackState.PlayingState and hasattr(self._player, "pause"):
            self._player.pause()
            self._set_status(f"Paused media: {self._current_media_title}", is_error=False)
        elif hasattr(self._player, "play"):
            self._player.play()
            self._set_status(f"Playing media: {self._current_media_title}", is_error=False)
        self._sync_playback_state()

    def _playback_state(self):
        if self._player is None or not hasattr(self._player, "playbackState"):
            return QMediaPlayer.PlaybackState.StoppedState
        return self._player.playbackState()

    def _sync_playback_state(self, *_args) -> None:
        is_playing = self._playback_state() == QMediaPlayer.PlaybackState.PlayingState
        self._play_btn.setText("PAUSE" if is_playing else "PLAY")

    def _sync_media_status(self, *_args) -> None:
        if not self._current_media_title:
            return
        self._set_status(f"Loaded {self._current_media_kind or 'media'}: {self._current_media_title}", is_error=False)

    def _on_position_changed(self, position: int) -> None:
        with QSignalBlocker(self._progress):
            self._progress.setValue(max(0, int(position or 0)))
        self._refresh_time_label(int(position or 0), self._progress.maximum())

    def _on_duration_changed(self, duration: int) -> None:
        total = max(0, int(duration or 0))
        with QSignalBlocker(self._progress):
            self._progress.setRange(0, total)
        self._refresh_time_label(self._progress.value(), total)

    def _refresh_time_label(self, position: int, duration: int) -> None:
        self._time_lbl.setText(f"{self._format_ms(position)} / {self._format_ms(duration)}")

    def _seek_media(self, position: int) -> None:
        if self._player is None or not self._current_media_path or not hasattr(self._player, "setPosition"):
            return
        self._player.setPosition(max(0, int(position or 0)))

    def _handle_error(self, *_args) -> None:
        error_text = ""
        if self._player is not None and hasattr(self._player, "errorString"):
            error_text = str(self._player.errorString() or "").strip()
        self._set_status(error_text or "Media playback failed.", is_error=True)

    def _set_status(self, text: str, *, is_error: bool) -> None:
        color = T.ERROR if is_error else T.DIM
        self._status_lbl.setText(str(text or "").strip())
        self._status_lbl.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
        )

    @staticmethod
    def _format_ms(value: int) -> str:
        total_seconds = max(0, int(value or 0)) // 1000
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
