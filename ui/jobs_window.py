from pathlib import Path
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QComboBox, QPushButton, QListWidget, QMessageBox
from jobs import JobStore
from storage import data_dir


class JobsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clicky Work — jobs and routines")
        self.resize(650, 650)
        self.store = JobStore()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Background answers use your selected model. Routines run only while Clicky is open.\nDesktop actions always need a separate Drive approval."))
        self.title = QLineEdit()
        self.title.setPlaceholderText("Job title")
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText("What should Clicky work on?")
        self.prompt.setMaximumHeight(110)
        self.schedule = QComboBox()
        for label, interval in (("Once",0),("Every 15 minutes",900),("Hourly",3600),("Daily",86400)):
            self.schedule.addItem(label, interval)
        for widget in (self.title, self.prompt, self.schedule):
            layout.addWidget(widget)
        add = QPushButton("Start job / routine")
        add.clicked.connect(self.add)
        layout.addWidget(add)
        self.items = QListWidget()
        self.items.currentRowChanged.connect(self.show_result)
        layout.addWidget(self.items)
        actions = QHBoxLayout()
        for label, callback in (("Retry / resume",lambda:self.act('retry')),("Pause",lambda:self.act('pause')),("Delete",lambda:self.act('delete')),("Open result folder",self.open_folder)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)
        layout.addWidget(self.result)
        self.rows = []
        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)

    def add(self):
        try:
            self.store.add(self.title.text(),self.prompt.toPlainText(),self.schedule.currentData())
            self.prompt.clear()
            self.refresh()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self,"Could not create job",str(exc))

    def refresh(self):
        selected = self.rows[self.items.currentRow()]['id'] if 0 <= self.items.currentRow() < len(self.rows) else None
        self.rows = self.store.list()
        self.items.blockSignals(True)
        self.items.clear()
        for i,row in enumerate(self.rows):
            self.items.addItem(f"{row['title']} — {row['state']}" + (' ↻' if row['interval'] else ''))
            if row['id'] == selected:
                self.items.setCurrentRow(i)
        self.items.blockSignals(False)
        self.show_result(self.items.currentRow())

    def show_result(self,index):
        if 0 <= index < len(self.rows):
            row = self.rows[index]
            self.result.setPlainText(row['error'] or row['result'] or row['prompt'])

    def act(self,action):
        index = self.items.currentRow()
        if 0 <= index < len(self.rows):
            self.store.action(self.rows[index]['id'],action)
            self.refresh()

    def open_folder(self):
        index = self.items.currentRow()
        if 0 <= index < len(self.rows):
            import os
            path = data_dir() / 'workspaces' / self.rows[index]['id']
            path.mkdir(parents=True,exist_ok=True)
            os.startfile(path)
