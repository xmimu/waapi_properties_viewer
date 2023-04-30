import json

from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
import qdarktheme


from waapi_support import MyClient, RootPath, WaapiObject, CannotConnectToWaapiException
import rc_wwise_icons

TREE_ITEM_DATA_ROLE = Qt.ItemDataRole.UserRole
TABLE_ITEM_DATA_ROLE = Qt.ItemDataRole.UserRole

ICONS = {
    'voice': 'waapi_support/object_icons/ObjectIcons_SoundVoice_nor.png',
    WaapiObject.BlendContainer: 'waapi_support/object_icons/ObjectIcons_SequenceContainer_nor.png',
    WaapiObject.WorkUnit: 'waapi_support/object_icons/ObjectIcons_Workunit_nor.png',
    WaapiObject.Folder: 'waapi_support/object_icons/ObjectIcons_Folder_nor.png',
    WaapiObject.Sound: 'waapi_support/object_icons/ObjectIcons_SoundFX_nor.png',
    WaapiObject.Event: 'waapi_support/object_icons/ObjectIcons_Event_nor.png',
    WaapiObject.SoundBank: 'waapi_support/object_icons/ObjectIcons_Soundbank_nor.png',
    WaapiObject.RandomSequenceContainer: 'waapi_support/object_icons/ObjectIcons_RandomContainer_nor.png',
    WaapiObject.ActorMixer: 'waapi_support/object_icons/ObjectIcons_ActorMixer_nor.png',
    WaapiObject.SourcePlugin: 'waapi_support/object_icons/ObjectIcons_SourcePlugin_nor.png',
    WaapiObject.AudioFileSource: 'waapi_support/object_icons/ObjectIcons_AudioFile_nor.png'
}


class Worker(QObject):
    sig_send_tree_items = Signal(list)
    sig_send_properties_data = Signal(list)
    sig_waapi_connect = Signal(str)
    sig_can_not_connect = Signal(str)
    sig_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.client: MyClient | None = None

    def check_connect(self):
        if isinstance(self.client, MyClient): return True
        try:
            self.client = MyClient()
            self.client_version = self.client.get_version()
            self.sig_waapi_connect.emit(f'Connect to WAAPI, wwise version: {self.client_version}')
            return True
        except CannotConnectToWaapiException:
            self.sig_can_not_connect.emit('Can not connect to WAAPI.')
        except Exception as e:
            self.sig_error.emit(e)

    def get_tree(self) -> None:
        if not self.check_connect(): return

        def get_icon(self, w_data):
            _type = w_data['type']
            icon_path = ICONS.get(_type, '')
            if _type == WaapiObject.Sound and self.client.get_property(w_data['id'], '@IsVoice'):
                icon_path = ICONS.get('voice', '')
            icon = QIcon(str(icon_path))
            return icon

        def add_node(self, parent_item, parent_path):
            for child in self.client.get_children(parent_path):
                child_item = QTreeWidgetItem()
                child_item.setData(0, TREE_ITEM_DATA_ROLE, child)
                child_item.setText(0, child['name'])
                child_item.setText(1, child['type'])
                child_item.setText(2, child['id'])
                child_item.setText(3, child['path'])

                icon = get_icon(self, child)
                child_item.setIcon(0, icon)
                parent_item.addChild(child_item)

                add_node(self, child_item, child['path'])

        items = []
        for path in RootPath.path_list():
            item = QTreeWidgetItem()
            item_path = str(path)
            item.setText(0, item_path.replace('\\', ''))
            icon = QIcon('waapi_support/object_icons/ObjectIcons_PhysicalFolder_nor.png')
            item.setIcon(0, icon)
            add_node(self, item, item_path)
            items.append(item)

        self.sig_send_tree_items.emit(items)

    def get_properties(self, id_list: list, input_properties: list = None):
        if not id_list: return
        data = []
        if input_properties is not None:
            for i in id_list:
                result = self.client.get(i, return_list=input_properties)
                data.append(result)
        else:
            for i in id_list:
                result = self.client.get_properties(i)
                data.append(result)

        if data:
            self.sig_send_properties_data.emit(data)

    def waapi_disconnect(self):
        if self.client is not None:
            self.client.disconnect()


class PropertyWindow(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = []
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Search property...')
        self.search_input.textChanged.connect(self.search)
        self.text_browser = QTextBrowser()
        layout = QVBoxLayout()
        layout.addWidget(self.search_input)
        layout.addWidget(self.text_browser)
        self.setLayout(layout)
        self.setStyleSheet('font:16px')
        self.resize(400, 400)
        self.setWindowTitle('Property Window')

    def set_data(self, data: list):
        self.text_browser.setText(json.dumps(data, ensure_ascii=False, indent=2))
        self.data = data
        self.show()

    def search(self):
        text = self.search_input.text().strip()
        if not text:
            self.set_data(self.data)
            return
        self.text_browser.clear()
        for i in self.data:
            for k, v in i.items():
                if text.lower() in str(k).lower():
                    self.text_browser.append(json.dumps({k:v},ensure_ascii=False,indent=2))


class Window(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.work_thread = QThread(self)
        self.worker = Worker(self)
        self.worker.moveToThread(self.work_thread)
        self.work_thread.start()
        self.find_result = []
        self.switch_index = 0
        self.is_empty_tree = True
        self.create_widgets()
        self.create_layouts()
        self.create_connections()
        # self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet('font:16px')
        self.resize(600, 800)

    def create_widgets(self):
        self.btn_connect = QPushButton('Connect/Refresh')
        self.btn_expand_all = QPushButton('Expand All')
        self.btn_collapse_all = QPushButton('Collapse All')

        self.btn_show_selected_properties = QPushButton('Show Selected Properties')

        self.edit_search = QLineEdit(self)
        self.btn_pre = QPushButton('<')
        self.btn_pre.setEnabled(False)
        self.btn_next = QPushButton('>')
        self.btn_next.setEnabled(False)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(['Name', 'Type', 'Id', 'Path'])
        self.tree.setColumnWidth(0, 400)
        self.tree.setColumnWidth(2, 400)

        # sub window
        self.property_window: PropertyWindow | None = PropertyWindow()

    def create_layouts(self):
        layout = QVBoxLayout()
        btn_tools_layout = QHBoxLayout()
        btn_tools_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        btn_tools_layout.addWidget(self.btn_connect)
        btn_tools_layout.addWidget(self.btn_expand_all)
        btn_tools_layout.addWidget(self.btn_collapse_all)
        btn_tools_layout.addWidget(self.btn_show_selected_properties)
        layout.addLayout(btn_tools_layout)

        search_bar_layout = QHBoxLayout()
        search_bar_layout.addWidget(self.btn_pre)
        search_bar_layout.addWidget(self.btn_next)
        search_bar_layout.addWidget(self.edit_search)
        layout.addLayout(search_bar_layout)
        layout.addWidget(self.tree)

        self.setLayout(layout)

    def create_connections(self):
        self.worker.sig_waapi_connect.connect(lambda x: print(x))
        self.worker.sig_error.connect(lambda x: print(x))
        self.worker.sig_can_not_connect.connect(lambda x: print(x))
        self.worker.sig_send_tree_items.connect(self.set_tree_data)
        self.worker.sig_send_properties_data.connect(self.show_property_widget)
        # button connections
        self.btn_connect.clicked.connect(self.refresh_tree)
        self.btn_expand_all.clicked.connect(self.tree.expandAll)
        self.btn_collapse_all.clicked.connect(self.tree.collapseAll)
        self.btn_show_selected_properties.clicked.connect(self.btn_show_selected_properties_clicked)
        # search bar
        self.btn_pre.clicked.connect(lambda: self.switch_to(self.switch_index - 1))
        self.btn_next.clicked.connect(lambda: self.switch_to(self.switch_index + 1))
        # tree widget
        self.edit_search.textChanged.connect(self.edit_search_text_changed)
        self.tree.itemClicked.connect(lambda x: print(x.text(0)))

    def set_tree_data(self, items):
        self.tree.addTopLevelItems(items)

    def set_switch_btn_enable(self, state: bool):
        self.btn_pre.setEnabled(state)
        self.btn_next.setEnabled(state)

    def init_find_result(self):
        self.find_result = []
        self.switch_index = 0
        self.set_switch_btn_enable(False)
        self.tree.clearSelection()

    def switch_to(self, index: int):
        # clear selection and select
        if not self.find_result: return
        if index >= len(self.find_result):
            index = 0
        if index < 0: index = len(self.find_result) - 1

        self.tree.clearSelection()
        self.find_result[index].setSelected(True)
        self.tree.scrollToItem(self.find_result[index])
        self.switch_index = index

    @Slot()
    def edit_search_text_changed(self, text):
        if not text:
            self.init_find_result()
            return

        result = self.tree.findItems(text, Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive, 0)

        if result:
            self.set_switch_btn_enable(True)
            self.find_result = result
            self.switch_to(0)

        else:
            self.init_find_result()

    def refresh_tree(self):
        self.tree.clear()
        self.worker.get_tree()

    @Slot()
    def btn_show_selected_properties_clicked(self):
        items = self.tree.selectedItems()
        id_list = [i.data(0, TREE_ITEM_DATA_ROLE)['id'] for i in items if i.data(0, TREE_ITEM_DATA_ROLE)]
        self.worker.get_properties(id_list)

    def show_property_widget(self, data: list[dict]):
        self.property_window.set_data(data)

    def showEvent(self, event):
        if self.is_empty_tree:
            self.refresh_tree()
            self.is_empty_tree = False

    def closeEvent(self, event):
        self.worker.waapi_disconnect()
        self.property_window.close()


if __name__ == '__main__':
    app = QApplication()
    qdarktheme.setup_theme()
    window = Window()
    window.setWindowTitle('WAAPI Properties Viewer')
    window.show()
    app.exec()

# with MyClient() as client:
#     sel_id = client.get_selected_objects()[0]['id']
#     print(client.get_property(sel_id,'@RandomOrSequence'))
#     client.disconnect()
