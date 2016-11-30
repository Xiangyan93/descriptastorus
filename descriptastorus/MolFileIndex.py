import os, numpy
from . import raw

class MolFileIndex:
    """Index for a molecule file to provide random access to the internal molecules.
    """
    
    def __init__(self, filename, indexDirectory,
                 smilesColumn=-1, nameColumn=-1, hasHeader=False, sep=None,
                 nameFxn=None
             ):
        """Fast random access to a smiles file by row index
        filename           = indexed file
        rawStoreDirectory  = RawStore of the indices

        OptionalData
        ------------
        smilesColumn = column used to extract the smileString = -1 if not smiles format
        hasHeader    = First entry is the header entry [False]
        sep          = seperator used to extract columns [None]
        nameFxn      = optional function to return the name of the indexed molecule

        Example
        -----------
        See MakeSmilesIndex and MakeSDF Index to make indexed files
        """
        self.db = raw.RawStore(indexDirectory)
        self.filename = filename
        self.hasHeader = hasHeader
        self.smilesColumn = smilesColumn
        self.nameColumn = nameColumn
        self.nameFxn = nameFxn
        
        if self.hasHeader:
            self.N = self.db.N - 3
        else:
            self.N = self.db.N - 2
        self.sep = sep
        # mmap?
        self.f = open(self.filename, 'r')
        
        if self.hasHeader:
            colnames = self.colnames = self._get(None)
        else:
            colnames = self.colnames = ["column_%d"%x for x in range(len(self._get(0)))]

        # get the first entry
        if self.hasHeader:
            row = self._get(1)
        else:
            row = self._get(0)
            
            
        if self.smilesColumn != -1:
            try:
                self.smilesColIdx = int(self.smilesColumn)
            except ValueError:
                self.smilesColIdx = colnames.index(self.smilesColumn)
                if self.smilesColIdx == -1:
                    raise IndexError("Specified smiles column %r name not in header"%
                                     self.smilesColumn)
            
            if len(row) <= self.smilesColIdx:
                raise IndexError("Smiles Column %d greater than rowsize %s\n"
                                 "Perhaps the seperator is mispecified (currently %r)"% (
                                     self.smilesColIdx,
                                     len(row),
                                     self.sep))

        if self.nameColumn != -1:
            try:
                self.nameidx = int(self.nameColumn)
            except ValueError:
                self.nameidx = colnames.index(self.nameColumn)

                if self.nameidx == -1:
                    raise IndexError("Specified name column name %r not in header"%
                                     self.nameColumn)

            if len(row) <= self.nameidx:
                raise IndexError("Name Column %d greater than rowsize %s\n"
                                 "Perhaps the seperator is mispecified (currently %r)"% (
                                     self.smilesColIdx,
                                     len(row),
                                     self.sep))
    def _get(self, idx):
        if idx is None:
            idx = 0
        elif self.hasHeader:
            idx += 1
            
        start = self.db.get(idx)[0]
        end = self.db.get(idx+1)[0]
        self.f.seek(start,0)
        buf = self.f.read(end-start-1)
        if self.sep:
            return buf.split(self.sep)
        return buf

    def header(self):
        """Return header column (throws ValueError if no header column is available)"""
        if self.hasHeader:
            return self._get(None)
        raise ValueError("Datastore doesn't have a header")
    
    def get(self, idx):
        """idx -> gets the data at row idx
        return a list if the data is a smiles like file
        returns a string buffer otherwise
        """
        if self.hasHeader:
            idx += 1
        return self._get(idx)
    
    def getMol(self, idx):
        if self.smilesColIdx != -1:
            return self._get(idx)[self.smilesColIdx]
        return self._get(idx)

    def getName(self, idx):
        if self.nameidx == -1:
            if self._nameGetter:
                return self._nameGetter(self._get(idx))
            
            raise ValueError("SmilesIndex does not have a name column or a name retriever")
        
        return self._get(idx)[self.nameidx]

def simplecount(filename):
    lines = 0
    for line in open(filename):
        lines += 1
    return lines

def index(fname, word):
    fsize = os.path.getsize(fname)
    bsize = 2**16
    
    with open(fname, 'rb') as f:

        buffer = None
        overlap = len(word) - 1
        while True:
            if (f.tell() >= overlap and f.tell() < fsize):
                f.seek(f.tell() - overlap)
            buffer = f.read(bsize)
            if buffer:
                pos = buffer.find(word)
                while pos != -1:
                    yield f.tell() - (len(buffer) - pos)
                    pos = buffer.find(word, pos+1)
                
            else:
                break
    
def MakeSmilesIndex(filename, dbdir, hasHeader, smilesColumn, nameColumn=-1, sep=None):
    """Make smiles index -> index a smiles file for random access"""
    sz = os.path.getsize(filename)
    
    N = simplecount(filename)
    if N < 2**8:
        dtype = numpy.uint8
    elif N < 2**16:
        dtype = numpy.uint16
    elif N < 2**32:
        dtype = numpy.uint32
    else:
        dtype = numpy.uint64

    db = raw.MakeStore([("index", dtype)], N+1, dbdir)

    # first row
    #  TODO sniff newline...
    db.putRow(0, [0])
    for i,pos in enumerate(index(filename, b"\n")):
        db.putRow(i+1, [pos+1])

    return MolFileIndex(filename, dbdir, smilesColumn,
                        nameColumn=nameColumn, hasHeader=hasHeader,
                        sep=sep)

def SDFNameGetter(buffer):
    return buffer.split("\n")[0].strip()

def MakeSDFIndex(filename, dbdir):
    """Make smiles index -> index a smiles file for random access"""
    sz = os.path.getsize(filename)
    
    N = simplecount(filename)
    if N < 2**8:
        dtype = numpy.uint8
    elif N < 2**16:
        dtype = numpy.uint16
    elif N < 2**32:
        dtype = numpy.uint32
    else:
        dtype = numpy.uint64

    # TODO sniff newline ...
    indices = list(index(filename, b"$$$$\n"))
    
    db = raw.MakeStore([("index", dtype)], N+1, dbdir)

    # first row
    db.putRow(0, [0])
    for i, idx in enumerate(indices):
        db.putRow(i+1, [pos+1])
    
    return MolFileIndex(filename, dbdir, nameFxn=SDFNameGetter)

        
