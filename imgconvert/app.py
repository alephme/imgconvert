from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QWidget,
)

from .converter import SUPPORTED_FORMATS, convert_file, detect_input_format


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ImgConvert")

        root = QWidget(self)
        self.setCentralWidget(root)

        layout = QGridLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("选择要转换的图片文件（.svg/.jpg/.png/.webp/.ico）")

        self.btn_browse_in = QPushButton("选择…")
        self.btn_browse_in.clicked.connect(self._pick_input)

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("选择输出路径")

        self.btn_browse_out = QPushButton("输出到…")
        self.btn_browse_out.clicked.connect(self._pick_output)

        self.format_combo = QComboBox()
        for fmt in SUPPORTED_FORMATS:
            self.format_combo.addItem(fmt.upper(), fmt)
        self.format_combo.currentIndexChanged.connect(self._suggest_output)

        self.btn_convert = QPushButton("开始转换")
        self.btn_convert.clicked.connect(self._convert)

        self.status = QLabel("")
        self.status.setWordWrap(True)

        layout.addWidget(QLabel("输入文件"), 0, 0)
        layout.addWidget(self.input_edit, 0, 1)
        layout.addWidget(self.btn_browse_in, 0, 2)

        layout.addWidget(QLabel("输出格式"), 1, 0)
        layout.addWidget(self.format_combo, 1, 1)

        layout.addWidget(QLabel("输出路径"), 2, 0)
        layout.addWidget(self.output_edit, 2, 1)
        layout.addWidget(self.btn_browse_out, 2, 2)

        layout.addWidget(self.btn_convert, 3, 0, 1, 3)
        layout.addWidget(self.status, 4, 0, 1, 3)

        layout.setColumnStretch(1, 1)

    def _pick_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择输入图片",
            "",
            "Images (*.svg *.png *.jpg *.jpeg *.webp *.ico);;All Files (*)",
        )
        if not path:
            return
        self.input_edit.setText(path)
        self._suggest_output()

    def _suggest_output(self) -> None:
        in_path = Path(self.input_edit.text().strip())
        if not in_path.suffix:
            return
        in_fmt = detect_input_format(in_path)
        if not in_fmt:
            return
        out_fmt = self.format_combo.currentData()
        if not out_fmt:
            return

        # If user already chose an output path, don't override.
        if self.output_edit.text().strip():
            out_path = Path(self.output_edit.text().strip())
            suggested = out_path.with_suffix("." + out_fmt)
            self.output_edit.setText(str(suggested))
            return

        suggested = in_path.with_suffix("." + out_fmt)
        self.output_edit.setText(str(suggested))

    def _pick_output(self) -> None:
        out_fmt = self.format_combo.currentData() or "png"
        default_suffix = "." + out_fmt

        default_path = self.output_edit.text().strip() or self.input_edit.text().strip()
        if default_path:
            base = str(Path(default_path))
        else:
            base = "output" + default_suffix

        path, _ = QFileDialog.getSaveFileName(
            self,
            "选择输出路径",
            base,
            f"{out_fmt.upper()} (*{default_suffix});;All Files (*)",
        )
        if not path:
            return
        self.output_edit.setText(path)

    def _convert(self) -> None:
        in_str = self.input_edit.text().strip()
        out_str = self.output_edit.text().strip()
        out_fmt = self.format_combo.currentData()

        if not in_str:
            QMessageBox.warning(self, "提示", "请选择输入文件")
            return
        if not out_str:
            QMessageBox.warning(self, "提示", "请选择输出路径")
            return
        if not out_fmt:
            QMessageBox.warning(self, "提示", "请选择输出格式")
            return

        result = convert_file(Path(in_str), Path(out_str), str(out_fmt))
        self.status.setText(result.message)
        if not result.ok:
            QMessageBox.critical(self, "转换失败", result.message)
            return

        QMessageBox.information(
            self,
            "转换完成",
            f"已生成：\n{result.output_path}",
        )


def main() -> int:
    app = QApplication([])
    app.setApplicationDisplayName("ImgConvert")

    w = MainWindow()
    w.resize(720, 220)
    w.show()

    return app.exec()
