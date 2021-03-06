from PyQt5.QtCore import pyqtSignal, QMimeData, QObject
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QIcon
from PyQt5.QtWidgets import QApplication, QAbstractItemView

from opcua import ua
from opcua import Node


class TreeWidget(QObject):

    error = pyqtSignal(str)

    def __init__(self, view):
        QObject.__init__(self, view)
        self.view = view
        self.model = TreeViewModel()
        self.model.clear()  # FIXME: do we need this?
        #self.model.error.connect(lambda x: self.error.emit(x))
        self.model.error.connect(self.error)
        self.view.setModel(self.model)
        #self.view.setUniformRowHeights(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.header().setSectionResizeMode(1)

    def clear(self):
        self.model.clear()

    def set_root_node(self, node):
        self.model.clear()
        self.model.set_root_node(node)

    def copy_path(self):
        path = self.get_current_path()
        path_str = ",".join(path)
        QApplication.clipboard().setText(path_str)

    def copy_nodeid(self):
        node = self.get_current_node()
        if node:
            text = node.nodeid.to_string()
        else:
            text = ""
        QApplication.clipboard().setText(text)

    def get_current_path(self):
        idx = self.view.currentIndex()
        idx = idx.sibling(idx.row(), 0)
        it = self.model.itemFromIndex(idx)
        path = []
        while it and it.data():
            node = it.data()
            name = node.get_browse_name().to_string()
            path.insert(0, name)
            it = it.parent()
        return path

    def reload_current(self):
        idx = self.view.currentIndex()
        idx = idx.sibling(idx.row(), 0)
        it = self.model.itemFromIndex(idx)
        if not it:
            return None
        for i in range(it.rowCount()):
            it.takeRow(0)
        node = it.data()
        if node:
            self.model.reload(node)


    def get_current_node(self, idx=None):
        if idx is None:
            idx = self.view.currentIndex()
        idx = idx.sibling(idx.row(), 0)
        it = self.model.itemFromIndex(idx)
        if not it:
            return None
        node = it.data()
        if not node:
            print("No node for item:", it, it.text())
            return None
        return node

    def add_node_to_current(self, node):
        idx = self.view.currentIndex()
        it = self.model.itemFromIndex(idx)
        self.model.add_item


class TreeViewModel(QStandardItemModel):

    error = pyqtSignal(str)

    def __init__(self):
        super(TreeViewModel, self).__init__()
        self._fetched = []

    def clear(self):
        QStandardItemModel.clear(self)
        self._fetched = []
        self.setHorizontalHeaderLabels(['DisplayName', "BrowseName", 'NodeId'])

    def set_root_node(self, node):
        desc = self._get_node_desc(node)
        self.add_item(desc, node=node)

    def _get_node_desc(self, node):
        attrs = node.get_attributes([ua.AttributeIds.DisplayName, ua.AttributeIds.BrowseName, ua.AttributeIds.NodeId, ua.AttributeIds.NodeClass])
        desc = ua.ReferenceDescription()
        desc.DisplayName = attrs[0].Value.Value
        desc.BrowseName = attrs[1].Value.Value
        desc.NodeId = attrs[2].Value.Value
        desc.NodeClass = attrs[3].Value.Value
        desc.TypeDefinition = ua.TwoByteNodeId(ua.ObjectIds.FolderType)
        return desc

    def add_item(self, desc, parent=None, node=None):
        item = [QStandardItem(desc.DisplayName.to_string()), QStandardItem(desc.BrowseName.to_string()), QStandardItem(desc.NodeId.to_string())]
        if desc.NodeClass == ua.NodeClass.Object:
            if desc.TypeDefinition == ua.TwoByteNodeId(ua.ObjectIds.FolderType):
                item[0].setIcon(QIcon(":/folder.svg"))
            else:
                item[0].setIcon(QIcon(":/object.svg"))
        elif desc.NodeClass == ua.NodeClass.Variable:
            if desc.TypeDefinition == ua.TwoByteNodeId(ua.ObjectIds.PropertyType):
                item[0].setIcon(QIcon(":/property.svg"))
            else:
                item[0].setIcon(QIcon(":/variable.svg"))
        elif desc.NodeClass == ua.NodeClass.Method:
            item[0].setIcon(QIcon(":/method.svg"))
        elif desc.NodeClass == ua.NodeClass.ObjectType:
            item[0].setIcon(QIcon(":/object_type.svg"))
        elif desc.NodeClass == ua.NodeClass.VariableType:
            item[0].setIcon(QIcon(":/variable_type.svg"))
        if node:
            item[0].setData(node)
        else:
            parent_node = parent.data()
            item[0].setData(Node(parent_node.server, desc.NodeId))
        if parent:
            return parent.appendRow(item)
        else:
            return self.appendRow(item)

    def reload(self, node):
        if node in self._fetched:
            self._fetched.remove(node)

    def canFetchMore(self, idx):
        item = self.itemFromIndex(idx)
        if not item:
            return True
        node = item.data()
        if node not in self._fetched:
            self._fetched.append(node)
            return True
        return False

    def hasChildren(self, idx):
        item = self.itemFromIndex(idx)
        if not item:
            return True
        node = item.data()
        if node in self._fetched:
            return QStandardItemModel.hasChildren(self, idx)
        return True

    def fetchMore(self, idx):
        parent = self.itemFromIndex(idx)
        if parent:
            self._fetchMore(parent)

    def _fetchMore(self, parent):
        try:
            descs = parent.data().get_children_descriptions()
            for desc in descs:
                self.add_item(desc, parent)
        except Exception as ex:
            self.error.emit(ex)
            raise

    #def flags(self, idx):
        #item = self.itemFromIndex(idx)
        #flags = QStandardItemModel.flags(self, idx)
        #if not item:
            #return flags
        #node = item.data()
        #if node and node.get_node_class() == ua.NodeClass.Variable:
            ## FIXME not efficient to query, should be stored in data()
            ##print(1, flags)
            #return flags | Qt.ItemIsDropEnabled
        #else:
            #print(2, flags)
            #return flags

    #def mimeTypes(self):
        #return ["application/vnd.text.list"]

    def mimeData(self, idxs):
        mdata = QMimeData()
        nodes = []
        for idx in idxs:
            item = self.itemFromIndex(idx)
            if item:
                node = item.data()
                if node:
                    nodes.append(node.nodeid.to_string())
        mdata.setText(", ".join(nodes))
        return mdata


