from PyQt5.QtCore import pyqtSlot, QThread, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QFileDialog
from ui.main_window_ui import Ui_MainWindow
from PyQt5.QtCore import pyqtSlot
import json
import datetime
import subprocess
from vosk import Model, KaldiRecognizer, SetLogLevel
from waitingspinnerwidget import QtWaitingSpinner


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        SetLogLevel(-1)
        self.model = Model("model")
        self.rec = KaldiRecognizer(self.model, 16000)
        self.rec.SetWords(True)

        self.api_thread = None
        self.file = None
        self.bad_words = []

        # spinner
        self.spinner = QtWaitingSpinner(self)
        self.spinner.setRoundness(70.0)
        self.spinner.setMinimumTrailOpacity(15.0)
        self.spinner.setTrailFadePercentage(70.0)
        self.spinner.setNumberOfLines(12)
        self.spinner.setLineLength(10)
        self.spinner.setLineWidth(5)
        self.spinner.setInnerRadius(10)
        self.spinner.setRevolutionsPerSecond(1)
        self.spinner.setColor(QColor(81, 4, 71))

    def closeEvent(self, event):
        super(QMainWindow, self).closeEvent(event)
        if self.api_thread:
            self.api_thread.exit(-1)
            self.api_thread.quit()
            self.api_thread.deleteLater()

    @pyqtSlot()
    def on_btnOpen_clicked(self):
        file = QFileDialog.getOpenFileName(
            self, "Open audio file", "", "Audios (*.m4a)"
        )[0]
        if not file:
            return
        self.file = file
        self.edtFilePath.setText(self.file)

    @pyqtSlot()
    def on_btnStart_clicked(self):
        if not self.file:
            QMessageBox.critical(self, "Error", "Please open audio file to detect.")
            return
        self.get_bad_words()
        if not len(self.bad_words):
            QMessageBox.critical(self, "Error", "Please type bad words.")
            return
        self.listResult.clear()
        self.centralWidget().setEnabled(False)

        self.api_thread = DetectorThread(
            self.file, self.bad_words, self.rec, parent=self
        )
        self.api_thread.finished.connect(self.onDetectingFinished)
        self.api_thread.finished.connect(self.api_thread.deleteLater)
        self.api_thread.progress.connect(self.onDetectingProgress)
        self.api_thread.start()
        self.spinner.start()

    def get_bad_words(self):
        text = " ".join(self.txtBadWords.toPlainText().lower().split())
        self.bad_words = [item.strip() for item in text.split(",")] if text else []

    def onDetectingFinished(self):
        self.spinner.stop()
        self.centralWidget().setEnabled(True)
        QMessageBox.information(
            self, "Info", "Finished detection.\nPlease check the result list."
        )

    def onDetectingProgress(self, info: str):
        if not info:
            return
        self.listResult.addItem(info)


class DetectorThread(QThread):
    finished = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, file, bad_words, rec, parent):
        super().__init__(parent)
        self.file = file
        self.bad_words = bad_words
        self.rec = rec
        self.process = None

    def check_json_result(self, jres):
        if not "result" in jres:
            return
        result = jres["result"]
        for item in result:
            word = item["word"]
            if word not in self.bad_words:
                continue
            conf = float(item["conf"])
            start = datetime.timedelta(seconds=item["start"]).split(".", 2)[0]
            end = datetime.timedelta(seconds=item["end"]).split(".", 2)[0]
            string = 'Word: "%s"    Start: %s    End: %s    Conf: %d' % (
                word,
                str(start),
                str(end),
                conf,
            )
            self.progress.emit(string)

    def run(self):
        if not self.process:
            self.process = subprocess.Popen(
                [
                    "ffmpeg",
                    "-loglevel",
                    "quiet",
                    "-i",
                    self.file,
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    "-f",
                    "s16le",
                    "-",
                ],
                stdout=subprocess.PIPE,
            )

        while True:
            data = self.process.stdout.read(4000)
            if len(data) == 0:
                break
            res = ""
            if self.rec.AcceptWaveform(data):
                res = self.check_json_result(json.loads(self.rec.Result()))
            self.progress.emit(res)
        res = self.check_json_result(json.loads(self.rec.FinalResult()))
        self.progress.emit(res)
        self.finished.emit()
