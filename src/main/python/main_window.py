import os
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

        self.model = None
        self.rec = None
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
            self.api_thread.terminate()
            self.api_thread.exit(-1)
            self.api_thread.quit()
            self.api_thread.deleteLater()

    @pyqtSlot()
    def on_btnLoadModel_clicked(self):
        if self.model:
            return
        self.statusBar().showMessage("Loading model...")
        self.spinner.start()
        self.centralWidget().setEnabled(False)
        self.model_thread = ModelLoadingThread(self)
        self.model_thread.finished.connect(self.onModelLoadingFinished)
        self.model_thread.start()

    def onModelLoadingFinished(self, model, rec):
        self.model = model
        self.rec = rec
        self.spinner.stop()
        self.centralWidget().setEnabled(True)
        self.statusBar().showMessage("Model prepaired")
        self.btnLoadModel.setEnabled(False)
        self.model_thread.terminate()
        self.model_thread.deleteLater()

    @pyqtSlot()
    def on_btnOpen_clicked(self):
        file = QFileDialog.getOpenFileName(
            self, "Open audio file", "", "Audio Files (*.m4a *.mp3 *.wma)"
        )[0]
        if not file:
            return
        self.file = file
        self.edtFilePath.setText(self.file)

    def get_bad_words(self):
        try:
            text = " ".join(self.txtBadWords.toPlainText().lower().split())
            self.bad_words = [item.strip() for item in text.split(",")] if text else []
        except Exception as err:
            QMessageBox.critical(self, "Error", err)

    @pyqtSlot()
    def on_btnStart_clicked(self):
        if not self.model:
            QMessageBox.critical(self, "Error", "Please load model first.")
            return
        if not self.file:
            QMessageBox.critical(self, "Error", "Please open audio file to detect.")
            return
        self.get_bad_words()
        if not len(self.bad_words):
            QMessageBox.critical(self, "Error", "Please type bad words.")
            return
        self.spinner.start()
        self.listResult.clear()
        self.centralWidget().setEnabled(False)
        self.statusBar().showMessage("Transcribing...")

        self.api_thread = DetectorThread(
            self.file, self.bad_words, self.rec, parent=self
        )
        self.api_thread.finished.connect(self.onDetectingFinished)
        self.api_thread.finished.connect(self.api_thread.deleteLater)
        self.api_thread.progress.connect(self.onDetectingProgress)
        self.api_thread.start()

    def onDetectingProgress(self, info: str):
        if not info:
            return
        self.listResult.addItem(info)

    def onDetectingFinished(self):
        self.api_thread.terminate()
        self.api_thread.deleteLater()
        self.spinner.stop()
        self.centralWidget().setEnabled(True)
        self.statusBar().showMessage("Detection is finished.")
        QMessageBox.information(
            self, "Info", "Finished detection.\nPlease check the result list."
        )


class ModelLoadingThread(QThread):
    finished = pyqtSignal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def run(self):
        SetLogLevel(0)
        model = Model("model")
        rec = KaldiRecognizer(model, 16000)
        rec.SetWords(True)
        self.finished.emit(model, rec)


class DetectorThread(QThread):
    finished = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, file, bad_words, rec, parent=None):
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
            if not [ele for ele in self.bad_words if (ele in word)]:
                continue
            try:
                conf = float(item["conf"])
                start = str(datetime.timedelta(seconds=item["start"])).split(".", 2)[0]
                end = str(datetime.timedelta(seconds=item["end"])).split(".", 2)[0]
                string = 'Word: "%s"    Start: %s    End: %s    Conf: %d' % (
                    word,
                    str(start),
                    str(end),
                    conf,
                )
                self.progress.emit(string)
            except Exception as err:
                with open("error.txt", "a") as f:
                    f.write(str(err) + "\n")

    def run(self):
        if not self.process:
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
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
                startupinfo=startupinfo,
            )

        while True:
            data = self.process.stdout.read(4000)
            if len(data) == 0:
                break
            res = ""
            if self.rec.AcceptWaveform(data):
                res = self.check_json_result(json.loads(self.rec.Result()))
        res = self.check_json_result(json.loads(self.rec.FinalResult()))
        self.finished.emit()
