import struct
from io import BytesIO
import hashlib

def unpack(fmt, buff):
    return struct.unpack(fmt, buff)[0]

def bytesToString(bytes):
    return bytes.decode('utf-8').rstrip('\0')

def readVLQU(stream):
    value = 0
    while True:
        tmp = ord(stream.read(1))
        value = (value << 7) | (tmp & 0x7f)
        if tmp & 0x80 == 0:
            break
    return value

class BlockFile:
    def __init__(self):
        self.blockStart = 0
        self.blockEnd = 0
        self.blockCount = 0
        self.blockSize = 1024
        self.file = None

    def setExtents(self, start, end):
        self.blockStart = start
        self.blockEnd = end

        if self.blockEnd < self.blockStart:
            self.blockEnd = self.blockStart

        self.blockCount = (self.blockEnd - self.blockStart) // self.blockSize

    def readBlock(self, blockIndex, blockOffset, size):
        if blockIndex > self.blockCount:
            raise Exception("blockIndex: {0} out of block range".format(blockIndex))

        blockOffset = min(self.blockSize, blockOffset)
        size = min(self.blockSize - blockOffset, size)

        if size <= 0:
            return None

        self.file.seek(self.blockStart + blockIndex * self.blockSize + blockOffset)
        return BytesIO(self.file.read(size))

class BlockStorage:
    HeaderMagic = 'SBBF02'
    PrefixHeaderSize = 32

    def __init__(self):
        self.isOpen = False
        self.headerSize = 256
        self.headFreeIndexBlock = None
        self.file = None
        self.blockFile = BlockFile()

    def checkIfOpen(self, methodName, mustBeOpen):
        if mustBeOpen and not self.isOpen:
            raise Exception("BlockStorage method '{0}' called when not open, must be open".format(methodName))

        if not mustBeOpen and self.isOpen:
            raise Exception("BlockStorage method '{0}' called when open, cannot call when open".format(methodName))

    def setHeaderSize(self, size):
        self.checkIfOpen('setHeaderSize', 0)
        self.headerSize = size

    def getUserHeaderSize(self):
        return self.headerSize - self.PrefixHeaderSize

    def readFromUserHeader(self, headerOffset, size):
        self.checkIfOpen('readFromUserHeader', 1)

        if (headerOffset + size) > self.getUserHeaderSize():
            raise Exception("BlockStorage.readFromUserHeader called outside of bounds of user header")

        self.file.seek(self.PrefixHeaderSize + headerOffset)
        return self.file.read(size)

    def readBlockExplicit(self, blockIndex, blockOffset, size):
        self.checkIfOpen('readBlockExplicit', 1)
        return self.blockFile.readBlock(blockIndex, blockOffset, size)

    def readBlock(self, blockIndex):
        return self.readBlockExplicit(blockIndex, 0, self.getBlockSize())

    def getBlockSize(self):
        return self.blockFile.blockSize

    def open(self):
        if self.isOpen:
            return 0

        if self.file is None:
            raise Exception('BlockStorage.open called with no file set')

        self.blockFile.file = self.file

        f = self.file

        f.seek(0)
        magic = bytesToString(f.read(6))
        if magic != self.HeaderMagic:
            raise Exception('File is not a valid BlockFile')

        self.headerSize = unpack('>i', f.read(4))
        self.blockFile.blockSize = unpack('>i', f.read(4))

        noFreeIndexBlock = unpack('?', f.read(1))
        if not noFreeIndexBlock:
            self.headFreeIndexBlock = unpack('>i', f.read(4))

        # I think if noFreeIndexBlock == True then we need recovery

        # Calculate file size - TODO: Hopefully this doesn't read in the file
        f.seek(0,2)
        fileSize = f.tell()

        self.blockFile.setExtents(self.headerSize, fileSize)

        self.isOpen = True


    def debugInfo(self):
        print('Header Size:', self.headerSize)
        print('Block Size:', self.blockFile.blockSize)
        print('Head Free Index Block:', self.headFreeIndexBlock)
        print('Block Start:', self.blockFile.blockStart)
        print('Block End:', self.blockFile.blockEnd)
        print('Block Count:', self.blockFile.blockCount)

class IndexElement:
    def __init__(self, k, p):
        self.key = k
        self.pointer = p

class IndexNode:
    def __init__(self):
        self.selfPointer = None
        self.level = None
        self.beginPointer = None
        self.pointers = []

    def size(self):
        if self.beginPointer is not None:
            return len(self.pointers) + 1
        else:
            return 0

    def pointer(self, i):
        if i == 0:
            return self.beginPointer
        else:
            return self.pointers[i - 1].pointer

    def debugInfo(self):
        print('Self Pointer:', self.selfPointer)
        print('Level:', self.level)
        print('Begin Poitner:', self.beginPointer)
        print('Pointers:', len(self.pointers))

class LeafElement:
    def __init__(self, k, d):
        self.key = k
        self.data = d

class LeafNode:
    def __init__(self):
        self.selfPointer = None
        self.nextLeaf = None
        self.elements = []

class LeafInputStream():
    def __init__(self, btree):
        self.btree = btree

    def read(self, n):
        return self.btree.readFromCurrentLeaf(n)

class BTreeDatabase:
    FileIdentifier = 'BTreeDB4'
    IndexMagic = 'II'
    LeafMagic = 'LL'

    def __init__(self):
        self.blockStorage = BlockStorage()
        self.rootIsLeaf = False
        self.rootPointer = None
        self.currentLeafBlock = None
        self.currentBuffer = None
        self.indexCache = {}

    # You must implement:
    # getKeySize(self)
    # getContentIdentifier(self)
    # readKey(self, buff)
    # readData(self, buff)

    def setFile(self, f):
        self.blockStorage.file = f

    def readRoot(self):
        unknownBool = unpack('?', self.blockStorage.readFromUserHeader(28, 1))

        offset = 38 if unknownBool else 30

        self.rootPointer = unpack('>I', self.blockStorage.readFromUserHeader(offset, 4))
        self.rootIsLeaf = unpack('?', self.blockStorage.readFromUserHeader(offset + 4, 1))

    def open(self):
        if self.blockStorage.isOpen:
            return

        self.blockStorage.setHeaderSize(512)
        self.blockStorage.open()

        fileID = bytesToString(self.blockStorage.readFromUserHeader(0, 12))
        if fileID != self.FileIdentifier:
            raise Exception(
                "DB file identifier does not match expected value of '{0}' (Got {1})".format(
                    self.FileIdentifier,
                    fileID
                )
            )

        contentID = bytesToString(self.blockStorage.readFromUserHeader(12, 12))
        if contentID != self.getContentIdentifier():
            raise Exception(
                "DB content identifier does not match expected value of '{0}' (Got {1})".format(
                    self.getContentIdentifier(),
                    contentID
                )
            )

        keySize = unpack('>I', self.blockStorage.readFromUserHeader(24, 4))
        if keySize != self.getKeySize():
            raise Exception(
                "DB content key size does not match expected value of '{0}' (Got {1})".format(
                    self.getKeySize(),
                    keySize
                )
            )

        self.readRoot()

    def getBlockSize(self):
        return self.blockStorage.getBlockSize()

    def readIndex(self, pointer):
        index = IndexNode()
        buff = self.blockStorage.readBlock(pointer)

        self.currentBuffer = buff

        magic = bytesToString(buff.read(2))
        if magic != self.IndexMagic:
            raise Exception("Error, incorrect index block signature.")

        index.selfPointer = pointer
        index.level = unpack('B', buff.read(1))

        numChildren = unpack('>i', buff.read(4))
        index.beginPointer = unpack('>i', buff.read(4))

        for i in range(numChildren):
            key = self.readKey(buff)
            pointer = unpack('>i', buff.read(4))
            index.pointers.append(IndexElement(key, pointer))

        return index

    def loadIndex(self, pointer):
        if pointer not in self.indexCache:
            index = self.readIndex(pointer)
            self.indexCache[pointer] = index
            return index
        else:
            return self.indexCache[pointer]

    def loadLeaf(self, pointer):
        leaf = LeafNode()
        self.currentLeafBlock = pointer

        buff = self.blockStorage.readBlock(pointer)
        self.currentBuffer = buff

        magic = bytesToString(buff.read(2))
        if magic != self.LeafMagic:
            raise Exception("Error, incorrect leaf block signature.")

        leaf.selfPointer = pointer

        leafInput = LeafInputStream(self)

        count = unpack('>i', leafInput.read(4))
        for i in range(count):
            key = self.readKey(leafInput)
            data = self.readData(leafInput)
            leaf.elements.append(LeafElement(key, data))

        return leaf

    def readFromCurrentLeaf(self, size):
        if self.currentLeafBlock is None: # or -1
            raise Exception("DERPY DERP")

        data = BytesIO()

        length = size
        while length > 0:
            # 4 here is pointer size
            if (self.currentBuffer.tell() + length) < (self.getBlockSize() - 4):
                data.write(self.currentBuffer.read(length))
                length = 0
            else:
                toRead = self.getBlockSize() - 4 - self.currentBuffer.tell()
                data.write(self.currentBuffer.read(toRead))
                length -= toRead

            if self.currentBuffer.tell() == (self.getBlockSize() - 4) and length > 0:
                self.currentLeafBlock = unpack('>i', self.currentBuffer.read(4))
                if self.currentLeafBlock != -1:
                    self.currentBuffer = self.blockStorage.readBlock(self.currentLeafBlock)

                    magic = bytesToString(self.currentBuffer.read(2))
                    if magic != self.LeafMagic:
                        raise Exception("Error, incorrect leaf block signature.")
                else:
                    self.currentLeafBlock = -1
                    return data.getvalue()

        return data.getvalue()

    def forAllNodesInIndex(self, index, visitor):
        visitor.visitIndex(index)

        for i in range(index.size()):
            if index.level != 0:
                self.forAllNodesInIndex(self.loadIndex(index.pointer(i)), visitor)
            else:
                visitor.visitLeaf(self.loadLeaf(index.pointer(i)))

    def forAllNodes(self, visitor):
        if not self.rootIsLeaf:
            self.forAllNodesInIndex(self.loadIndex(self.rootPointer), visitor)
        else:
            visitor.visitLeaf(self.loadLeaf(self.rootPointer))

class SimpleDatabase(BTreeDatabase):
    def __init__(self, keySize, contentID):
        super().__init__()
        self.contentIdentifier = contentID
        self.keySize = keySize

    def getKeySize(self):
        return self.keySize

    def getContentIdentifier(self):
        return self.contentIdentifier

    def readKey(self, buff):
        return buff.read(self.keySize)

    def readData(self, buff):
        size = readVLQU(buff)
        return buff.read(size)

glblIndex = hashlib.sha256('_index'.encode('utf-8')).digest()

def unpackStringList(data):
    stream = BytesIO(data)
    count = readVLQU(stream)
    strings = []
    for i in range(count):
        strLen = readVLQU(stream)
        strings.append(stream.read(strLen).decode('utf-8'))
    return strings

class Visitor:
    def visitLeaf(self, leaf):
        #print('Visiting leaf', leaf.selfPointer)
        for elem in leaf.elements:
            if elem.key == glblIndex:
                print(leaf.selfPointer)
                print(len(elem.data))
                strings = unpackStringList(elem.data)
                f = open('out.txt', 'w')
                f.write('\n'.join(strings))
                f.close()


    def visitIndex(self, index):
        pass

if __name__ == '__main__':
    db = SimpleDatabase(32, 'Assets1')
    db.setFile(open('C:\\SSDSteam\\SteamApps\\common\\Starbound\\assets\\packed.pak', 'rb'))
    db.open()

    db.blockStorage.debugInfo()

    db.forAllNodes(Visitor())

