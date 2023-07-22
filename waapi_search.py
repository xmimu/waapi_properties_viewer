import sys
from typing import Optional
import qdarktheme
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

from waapi_support import MyClient


class Worker(QThread):
    sig_send_search_result = Signal(list)

    def __init__(self, parent: 'Window' = None, search_text=''):
        super().__init__(parent)
        self.parent = parent
        self.search_text = search_text

    def run(self) -> None:
        result = self.parent.waapi_client.get(self.search_text)
        self.sig_send_search_result.emit(result)

    def __del__(self):
        print('thread del...')


class Window(QWidget):
    sig_start_update_time = Signal()

    def __init__(self):
        super().__init__()
        self.type_list = []
        self.check_list = []
        self.result_result = []
        self.waapi_client: Optional[MyClient] = None
        self.create_widgets()
        self.create_layouts()
        self.create_connections()
        self.connect_waapi()

    def create_widgets(self):
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText('Search...')
        self.btn_group = QButtonGroup()
        self.btn_group.setExclusive(False)
        self.table = QTableWidget()
        # self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        # self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setRowCount(5)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['Name', 'Type', 'Notes', 'Path', 'ID'])

    def create_layouts(self):
        self.main_layout = QVBoxLayout()
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.main_layout.addWidget(self.edit_search)
        self.type_btn_layout = QHBoxLayout()
        self.type_btn_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.main_layout.addLayout(self.type_btn_layout)
        self.main_layout.addWidget(self.table)
        self.setLayout(self.main_layout)

    def create_connections(self):
        self.edit_search.textChanged.connect(self.search)
        self.table.cellClicked.connect(self.cell_clieked)

    def update_type_buttons(self):
        for type_name in self.type_list:  # type:str
            for check_box in self.btn_group.buttons():  # type:QCheckBox
                if type_name == check_box.text(): break
            else:
                new_check_box = QCheckBox(type_name)
                new_check_box.stateChanged.connect(self.on_type_checked)
                self.btn_group.addButton(new_check_box)
                self.type_btn_layout.addWidget(new_check_box)

    def connect_waapi(self):
        try:
            self.waapi_client = MyClient()
        except Exception as e:
            QMessageBox.warning(self, 'Warning', f'WAAPI 连接失败！\n{e}')
            self.setDisabled(True)

    def disconnect_waapi(self):
        if self.waapi_client:
            self.waapi_client.disconnect()

    def search(self):
        text = self.edit_search.text().strip()
        if not text:
            self.table.setRowCount(0)
            return
        self.worker = Worker(self, text)
        self.worker.sig_send_search_result.connect(self.update_search_result)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def update_search_result(self, result: list):
        result.sort(key=lambda x: x['type'])
        self.result_result = result

        # 去掉没选中的check box
        for i in self.btn_group.buttons():
            if not i.isChecked():
                self.btn_group.removeButton(i)
                self.type_list.remove(i.text())
                i.deleteLater()

        self.table.setRowCount(0)
        for data in result:
            _type = data['type']
            if _type not in self.type_list:
                self.type_list.append(_type)

            if self.check_list and _type not in self.check_list:
                continue

            row_index = self.table.rowCount()
            self.table.insertRow(self.table.rowCount())

            self.table.setItem(row_index, 0, QTableWidgetItem(data['name']))
            self.table.setItem(row_index, 1, QTableWidgetItem(data['type']))
            self.table.setItem(row_index, 2, QTableWidgetItem(data['notes']))
            self.table.setItem(row_index, 3, QTableWidgetItem(data['path']))
            self.table.setItem(row_index, 4, QTableWidgetItem(data['id']))

        self.update_type_buttons()

    def on_type_checked(self, state: bool):
        self.check_list = [i.text() for i in self.btn_group.buttons() if i.isChecked()]

        self.update_search_result(self.result_result)

    def cell_clieked(self, row, col):
        item = self.table.item(row,4)
        if item:
            id_str = item.text().strip()
            if id_str:
                self.waapi_client.go_to_sync_group([id_str])

    def closeEvent(self, event: QCloseEvent) -> None:
        self.disconnect_waapi()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    qdarktheme.setup_theme()
    window = Window()
    window.setWindowTitle('Wwise Search')
    window.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
    window.resize(600, 800)
    window.show()
    app.exec()
