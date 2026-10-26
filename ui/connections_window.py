"""Pair the browser and inspect user-supplied app tools without hidden execution."""
import json
import sys
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QComboBox,QPushButton,QPlainTextEdit,QMessageBox,QTabWidget

from storage import setting
from connectors import save_connector, remove_connector, MCPConnection
from browser_bridge import pairing_token


class ConnectionsWindow(QWidget):
    result_ready = pyqtSignal(str)
    tools_ready = pyqtSignal(object)

    def __init__(self,manager):
        super().__init__()
        self.manager = manager
        self.connection = None
        self.setWindowTitle('Clicky Connections')
        self.resize(700,650)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        browser = QWidget()
        b = QVBoxLayout(browser)
        note = QLabel('In Chrome/Edge/Brave, open the extensions page, enable Developer mode, then Load unpacked and select Clicky’s browser_extension folder. Paste this pairing code into its popup. Keep Clicky open. The connection stays on this PC.')
        note.setWordWrap(True)
        b.addWidget(note)
        code = QLineEdit(pairing_token())
        code.setReadOnly(True)
        code.setEchoMode(QLineEdit.EchoMode.Password)
        b.addWidget(code)
        copy = QPushButton('Copy pairing code')
        copy.clicked.connect(lambda:__import__('PyQt6.QtWidgets',fromlist=['QApplication']).QApplication.clipboard().setText(code.text()))
        b.addWidget(copy)
        folder = QPushButton('Open extension folder')
        folder.clicked.connect(self.open_extension)
        b.addWidget(folder)
        self.operation = QComboBox()
        self.operation.addItems(['snapshot','tabs','open','click','fill','press','scroll','back'])
        b.addWidget(self.operation)
        self.browser_args = QPlainTextEdit('{}')
        self.browser_args.setPlaceholderText('JSON arguments: ref and epoch from the latest snapshot; text for fill; url for open')
        b.addWidget(self.browser_args)
        execute = QPushButton('Review browser request')
        execute.clicked.connect(self.browser_request)
        b.addWidget(execute)
        tabs.addTab(browser,'Browser')

        tools = QWidget()
        t = QVBoxLayout(tools)
        t.addWidget(QLabel('Connect a Streamable HTTP MCP endpoint (2025-06-18).\nBrowser OAuth, stdio servers and hosted service catalogs are not included.'))
        self.name = QLineEdit(); self.name.setPlaceholderText('Connection name')
        self.url = QLineEdit(); self.url.setPlaceholderText('https://your-service.example/mcp')
        self.token = QLineEdit(); self.token.setPlaceholderText('Optional bearer token'); self.token.setEchoMode(QLineEdit.EchoMode.Password)
        for field in (self.name,self.url,self.token):t.addWidget(field)
        add = QPushButton('Save connection')
        add.clicked.connect(self.add)
        t.addWidget(add)
        self.connections = QComboBox()
        self.connections.currentIndexChanged.connect(self.selection_changed)
        t.addWidget(self.connections)
        controls = QHBoxLayout()
        for text,callback in [('List tools',self.list_tools),('Remove connection',self.remove)]:
            button = QPushButton(text); button.clicked.connect(callback); controls.addWidget(button)
        t.addLayout(controls)
        self.tools = QComboBox(); t.addWidget(self.tools)
        self.arguments = QPlainTextEdit('{}'); t.addWidget(self.arguments)
        call = QPushButton('Review tool call'); call.clicked.connect(self.call_tool); t.addWidget(call)
        tabs.addTab(tools,'App tools')
        shared=QWidget();shared_layout=QVBoxLayout(shared)
        warning=QLabel('Shared sessions send answers over your local network. Use only on a trusted LAN; the connection is not encrypted. They never share desktop control. Hosting may prompt Windows Firewall. Replace YOUR-LAN-IP in the host link before sharing it.')
        warning.setWordWrap(True);shared_layout.addWidget(warning)
        host=QPushButton('Host a trusted-LAN session');host.clicked.connect(manager.collab_start_host);shared_layout.addWidget(host)
        self.session_link=QLineEdit();self.session_link.setPlaceholderText('Paste a Clicky session link');shared_layout.addWidget(self.session_link)
        join=QPushButton('Join session');join.clicked.connect(lambda:manager.collab_join(self.session_link.text().strip()));shared_layout.addWidget(join)
        stop=QPushButton('Stop sharing');stop.clicked.connect(manager.collab_stop);shared_layout.addWidget(stop)
        self.shared_text=QPlainTextEdit();self.shared_text.setReadOnly(True);shared_layout.addWidget(self.shared_text)
        tabs.addTab(shared,'Shared session')
        self.result = QPlainTextEdit(); self.result.setReadOnly(True); layout.addWidget(self.result)
        attach = QPushButton('Use this result as chat context'); attach.clicked.connect(self.attach); layout.addWidget(attach)
        self.result_ready.connect(self.result.setPlainText)
        self.tools_ready.connect(self.show_tools)
        self.reload()

    def open_extension(self):
        import os
        root = Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
        os.startfile(root / 'browser_extension')

    def reload(self):
        self.connections.clear()
        for row in setting('connectors',[]):self.connections.addItem(row['name'],row)

    def add(self):
        try:
            save_connector(self.name.text(),self.url.text(),self.token.text())
            self.token.clear();self.reload()
        except (ValueError,OSError) as exc:QMessageBox.warning(self,'Connection not saved',str(exc))

    def remove(self):
        row = self.connections.currentData()
        if row:
            self.manager._connector_catalog.pop(row['id'],None)
            remove_connector(row['id']);self.connection=None;self.tools.clear();self.reload()

    def selection_changed(self):
        self.connection = None
        if hasattr(self,'tools'):
            self.tools.clear()

    def run(self,coro):
        future = self.manager._submit(coro)
        if future:
            def done(f):
                try:self.result_ready.emit(json.dumps(f.result(),ensure_ascii=False,indent=2))
                except Exception as exc:self.result_ready.emit(str(exc))
            future.add_done_callback(done)

    def list_tools(self):
        row = self.connections.currentData()
        if row:
            connection = MCPConnection(row)
            async def fetch():
                tools = await connection.connect()
                self.tools_ready.emit((connection,tools))
                return tools
            self.run(fetch())

    def show_tools(self,value):
        connection,tools = value
        row = self.connections.currentData()
        if not row or row['id'] != connection.config['id']:
            return
        self.connection = connection
        self.tools.clear()
        for tool in tools:self.tools.addItem(tool.get('name',''),tool)
        if self.connection:
            self.manager._connector_catalog[self.connection.config['id']] = {'name':self.connection.config['name'],'tools':[{'name':tool.get('name'),'description':tool.get('description','')[:300],'inputSchema':tool.get('inputSchema',{})} for tool in tools]}

    def confirm(self,title,value):
        return QMessageBox.question(self,title,json.dumps(value,ensure_ascii=False,indent=2)[:10000]+'\n\nThis request may change data in your connected service. Run it?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes

    def call_tool(self):
        try:
            if not self.connection or not self.tools.currentData():raise ValueError('List the tools for a connection first')
            arguments = json.loads(self.arguments.toPlainText())
            name = self.tools.currentData()['name']
            if self.confirm('Review app tool request',{'connection':self.connection.config['name'],'tool':name,'arguments':arguments}):
                self.run(self.connection.call(name,arguments))
        except ValueError as exc:QMessageBox.warning(self,'Invalid tool request',str(exc))

    def browser_request(self):
        try:
            args = json.loads(self.browser_args.toPlainText())
            if not isinstance(args,dict) or 'operation' in args or 'id' in args:raise ValueError('Use a JSON object of operation arguments')
            operation = self.operation.currentText()
            if operation in {'snapshot','tabs'} or self.confirm('Review browser request',{'operation':operation,**args}):
                self.run(self.manager._browser.command(operation,**args))
        except ValueError as exc:QMessageBox.warning(self,'Invalid browser request',str(exc))

    def attach(self):
        text = self.result.toPlainText().strip()
        if text:
            self.manager._attached_docs = (self.manager._attached_docs + [('connected-result.txt',text[:16000])])[-3:]
            self.result_ready.emit('Result attached to your next chat question.\n\n'+text)
