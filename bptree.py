# ================================
# B+ TREE NODE
# ================================
class BPlusTreeNode:
    def __init__(self, leaf=False):
        self.leaf = leaf
        self.keys = []
        self.values = []      # for leaf nodes
        self.children = []    # for internal nodes
        self.next = None      # leaf linking


# ================================
# B+ TREE
# ================================
class BPlusTree:
    def __init__(self, order=3):
        self.root = BPlusTreeNode(leaf=True)
        self.order = order


    # -------- SEARCH --------
    def search(self, key):
        node = self.root

        while not node.leaf:
            i = 0
            while i < len(node.keys) and key >= node.keys[i]:
                i += 1
            node = node.children[i]

        for i, k in enumerate(node.keys):
            if k == key:
                return node.values[i]

        return None


    # -------- INSERT --------
    def insert(self, key, value):
        root = self.root

        if len(root.keys) == self.order:
            new_root = BPlusTreeNode(leaf=False)
            new_root.children.append(root)
            self._split_child(new_root, 0)
            self.root = new_root

        self._insert_non_full(self.root, key, value)


    def _insert_non_full(self, node, key, value):

        if node.leaf:
            i = 0
            while i < len(node.keys) and node.keys[i] < key:
                i += 1
            node.keys.insert(i, key)
            node.values.insert(i, value)

        else:
            i = 0
            while i < len(node.keys) and key >= node.keys[i]:
                i += 1

            if len(node.children[i].keys) == self.order:
                self._split_child(node, i)

                if key >= node.keys[i]:
                    i += 1

            self._insert_non_full(node.children[i], key, value)


    # -------- SPLIT --------
    def _split_child(self, parent, index):

        node = parent.children[index]
        new_node = BPlusTreeNode(leaf=node.leaf)

        mid = len(node.keys) // 2

        if node.leaf:
            new_node.keys = node.keys[mid:]
            new_node.values = node.values[mid:]

            node.keys = node.keys[:mid]
            node.values = node.values[:mid]

            new_node.next = node.next
            node.next = new_node

            parent.keys.insert(index, new_node.keys[0])

        else:
            parent.keys.insert(index, node.keys[mid])

            new_node.keys = node.keys[mid + 1:]
            new_node.children = node.children[mid + 1:]

            node.keys = node.keys[:mid]
            node.children = node.children[:mid + 1]

        parent.children.insert(index + 1, new_node)


    # -------- UPDATE --------
    def update(self, key, new_value):
        node = self.root

        while not node.leaf:
            i = 0
            while i < len(node.keys) and key >= node.keys[i]:
                i += 1
            node = node.children[i]

        for i, k in enumerate(node.keys):
            if k == key:
                node.values[i] = new_value
                return True

        return False


    # -------- RANGE QUERY --------
    def range_query(self, start, end):
        node = self.root

        while not node.leaf:
            i = 0
            while i < len(node.keys) and start >= node.keys[i]:
                i += 1
            node = node.children[i]

        result = []

        while node:
            for i, key in enumerate(node.keys):
                if key > end:
                    return result
                if start <= key <= end:
                    result.append(node.values[i])
            node = node.next

        return result


    # -------- GET ALL (KEY, VALUE) --------
    def get_all(self):
        node = self.root

        while not node.leaf:
            node = node.children[0]

        result = []

        while node:
            for i in range(len(node.keys)):
                result.append((node.keys[i], node.values[i]))
            node = node.next

        return result


    # -------- GET ONLY KEYS (IMPORTANT FOR VALIDATION) --------
    def get_all_keys(self):
        node = self.root

        # go to leftmost leaf
        while not node.leaf:
            node = node.children[0]

        keys = []

        while node:
            keys.extend(node.keys)
            node = node.next

        return keys


    # -------- DELETE --------
    def delete(self, key):
        self._delete(self.root, key)

        if not self.root.leaf and len(self.root.keys) == 0:
            self.root = self.root.children[0]


    def _delete(self, node, key):

        if node.leaf:
            if key in node.keys:
                idx = node.keys.index(key)
                node.keys.pop(idx)
                node.values.pop(idx)
            return

        i = 0
        while i < len(node.keys) and key >= node.keys[i]:
            i += 1

        child = node.children[i]
        min_keys = (self.order + 1) // 2 - 1

        if len(child.keys) == min_keys:
            self._fill_child(node, i)
            if i >= len(node.children):
                i = len(node.children) - 1

        self._delete(node.children[i], key)


    def _fill_child(self, node, index):

        min_keys = (self.order + 1) // 2 - 1

        if index > 0 and len(node.children[index - 1].keys) > min_keys:
            self._borrow_from_prev(node, index)

        elif index < len(node.children) - 1 and len(node.children[index + 1].keys) > min_keys:
            self._borrow_from_next(node, index)

        else:
            if index < len(node.children) - 1:
                self._merge(node, index)
            else:
                self._merge(node, index - 1)


    def _borrow_from_prev(self, node, index):

        child = node.children[index]
        sibling = node.children[index - 1]

        if child.leaf:
            child.keys.insert(0, sibling.keys.pop())
            child.values.insert(0, sibling.values.pop())

            node.keys[index - 1] = child.keys[0]

        else:
            child.keys.insert(0, node.keys[index - 1])
            node.keys[index - 1] = sibling.keys.pop()

            child.children.insert(0, sibling.children.pop())


    def _borrow_from_next(self, node, index):

        child = node.children[index]
        sibling = node.children[index + 1]

        if child.leaf:
            child.keys.append(sibling.keys.pop(0))
            child.values.append(sibling.values.pop(0))

            node.keys[index] = sibling.keys[0]

        else:
            child.keys.append(node.keys[index])
            node.keys[index] = sibling.keys.pop(0)

            child.children.append(sibling.children.pop(0))


    def _merge(self, node, index):

        child = node.children[index]
        sibling = node.children[index + 1]

        if child.leaf:
            child.keys.extend(sibling.keys)
            child.values.extend(sibling.values)
            child.next = sibling.next

        else:
            child.keys.append(node.keys[index])
            child.keys.extend(sibling.keys)
            child.children.extend(sibling.children)

        node.keys.pop(index)
        node.children.pop(index + 1)