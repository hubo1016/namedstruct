'''
Created on 2015/7/8

:author: hubo
'''
from __future__ import print_function, absolute_import, division 
import struct
import logging
import warnings
try:
    from collections import OrderedDict as OrderedDict
except Exception:
    _has_ordered_dict = False
    OrderedDict = dict
else:
    _has_ordered_dict = True

class ParseError(ValueError):
    '''
    Base class for error in parsing
    '''
    pass

class BadLenError(ParseError):
    '''
    Data size does not match struct length
    '''
    pass

class BadFormatError(ParseError):
    '''
    Error in data format
    '''
    pass

def _set(obj, name, value):
    object.__setattr__(obj, name, value)

class NamedStruct(object):
    '''
    Store a binary struct message, which is serializable.
    
    There are external interfaces for general usage as well as internal interfaces reserved for parser.
    See doc for each interface.
    
    All the interface names start with _ to preserve normal names for fields.
    '''
    _pickleTypes = {}
    _pickleNames = {}
    _logger = logging.getLogger(__name__ + '.NamedStruct')
    def __init__(self, parser):
        '''
        Constructor. Usually a NamedStruct is constructed automatically by a parser, you should not call
        the initializer yourself.
        
        :param parser: parser to pack/unpack the struct
        
        :param inlineparent: if not None, this struct is embedded into another struct. An embedded struct
                acts like an agent to inlineparent - attributes are read from and stored into inlineparent.
        
        '''
        _set(self, '_parser', parser)
        _set(self, '_target', self)
    def _create_embedded_indices(self):
        '''
        Create indices for all the embedded structs. For parser internal use.
        '''
        try:
            _set(self, '_embedded_indices', dict((k,(self,v)) for k,v in getattr(self._parser.typedef, 'inline_names', {}).items()))
        except AttributeError:
            _set(self, '_embedded_indices', {})
    def _unpack(self, data):
        '''
        Unpack a struct from bytes. For parser internal use.
        '''
        #self._logger.log(logging.DEBUG, 'unpacking %r', self)
        current = self
        while current is not None:
            data = current._parser.unpack(data, current)
            last = current
            current = getattr(current, '_sub', None)
        _set(last, '_extra', data)
    def _pack(self):
        '''
        Pack current struct into bytes. For parser internal use.
        
        :returns: packed bytes
        
        '''
        #self._logger.log(logging.DEBUG, 'packing %r', self)
        ps = []
        current = self
        while current is not None:
            ps.append(current._parser.pack(current))
            last = current
            current = getattr(current, '_sub', None)
        ps.append(getattr(last, '_extra', b''))
        return b''.join(ps)
    def _prepack(self):
        '''
        Prepack stage. For parser internal use.
        '''
        current = self
        while current is not None:
            current._parser.prepack(current)
            current = getattr(current, '_sub', None)        
    def _tobytes(self, skipprepack = False):
        '''
        Convert the struct to bytes. This is the standard way to convert a NamedStruct to bytes.
        
        :param skipprepack: if True, the prepack stage is skipped. For parser internal use.
        
        :returns: converted bytes
        '''
        if not skipprepack:
            self._prepack()
        data = self._pack()
        paddingSize = self._parser.paddingsize2(len(data))
        return data + b'\x00' * (paddingSize - len(data))
    def _realsize(self):
        '''
        Get the struct size without padding (or the "real size")
        
        :returns: the "real size" in bytes
        
        '''
        current = self
        size= 0
        while current is not None:
            size += current._parser.sizeof(current)
            last = current
            current = getattr(current, '_sub', None)
        size += len(getattr(last, '_extra', b''))
        return size
    def __len__(self):
        '''
        Get the struct size with padding. Usually this aligns a struct into 4-bytes or 8-bytes boundary.
        
        :returns: padded size of struct in bytes
        
        '''
        return self._parser.paddingsize(self)
    def _subclass(self, parser):
        '''
        Create sub-classed struct from extra data, with specified parser. For parser internal use.
        
        :param parser: parser of subclass 
        '''
        _set(self, '_sub', parser._create(getattr(self, '_extra', b''), self._target))
        try:
            object.__delattr__(self, '_extra')
        except:
            pass
    def _autosubclass(self):
        '''
        Subclass a struct. When you modified some fields of a base class, you can create sub-classes with
        this method.
        '''
        self._parser.subclass(self)
    def _extend(self, newsub):
        '''
        Append a subclass (extension) after the base class. For parser internal use.
        '''
        current = self
        while hasattr(current, '_sub'):
            current = current._sub
        _set(current, '_sub', newsub)
        try:
            object.__delattr__(self, '_extra')
        except:
            pass
    def _gettype(self):
        '''
        Return current type of this struct
        
        :returns: a typedef object (e.g. nstruct)
        
        '''
        current = self
        lastname = getattr(current._parser, 'typedef', None)
        while hasattr(current, '_sub'):
            current = current._sub
            tn = getattr(current._parser, 'typedef', None)
            if tn is not None:
                lastname = tn
        return lastname
    def _getbasetype(self):
        '''
        Return base type of this struct
        
        :returns: a typedef object (e.g. nstruct)
        
        '''
        return getattr(self._parser, 'typedef', None)
    def _setextra(self, extradata):
        '''
        Set the _extra field in the struct, which stands for the additional ("extra") data after the
        defined fields.
        '''
        current = self
        while hasattr(current, '_sub'):
            current = current._sub
        _set(current, '_extra', extradata)
    def _getextra(self):
        '''
        Get the extra data of this struct.
        '''
        current = self
        while hasattr(current, '_sub'):
            current = current._sub
        return getattr(current, '_extra', None)
    def _validate(self, recursive = True):
        '''
        **DEPRECATED** structs are always unpacked now. _validate do nothing.
        
        Force a unpack on this struct to check if there are any format errors. Sometimes a struct is not
        unpacked until attributes are read from it, if there are format errors in the original data, a
        BadFormatError is raised. Call _validate to ensure that the struct is fully well-formatted.
        
        :param recursive: if True (default), also validate all sub-fields.
        '''
        pass
                        
    def __copy__(self):
        '''
        Create a copy of the struct. It is always a deepcopy, in fact it packs the struct and unpack it again.
        '''
        return self._parser.create(self._tobytes(), None)
    def __deepcopy__(self, memo):
        '''
        Create a copy of the struct.
        '''
        return self._parser.create(self._tobytes(), None)
    def __repr__(self, *args, **kwargs):
        '''
        Return the representation of the struct.
        '''
        t = self._gettype()
        if t is None:
            return object.__repr__(self, *args, **kwargs)
        else:
            return '<%r at %016X>' % (t, id(self))
    def __getstate__(self):
        '''
        Try to pickle the struct. Register the typedef of the struct to make sure it can be pickled and
        transfered with the type information. Actually it transfers the packed bytes and the type name.
        '''
        t = self._parser.typedef
        if t is not None and t in NamedStruct._pickleNames:
            return (self._tobytes(), NamedStruct._pickleNames[t], self._target)
        else:
            return (self._tobytes(), self._parser, self._target)
    def __setstate__(self, state):
        '''
        Restore from pickled value.
        '''
        if not isinstance(state, tuple):
            raise ValueError('State should be a tuple')
        t = state[1]
        if t in NamedStruct._pickleTypes:
            parser = NamedStruct._pickleTypes[t].parser()
        else:
            parser = t
        if state[2] is not self:
            type(self).__init__(self, parser, state[2])
        else:
            type(self).__init__(self, parser)
        self._unpack(state[0])
        if hasattr(self._parser, 'subclass'):
            self._parser.subclass(self)
    def _replace_embedded_type(self, name, newtype):
        '''
        Replace the embedded struct to a newly-created struct of another type (usually based on the
        original type). The attributes of the old struct is NOT preserved.
        
        :param name: either the original type, or the name of the original type. It is always the type
                     used in type definitions, even if it is already replaced once or more.
                     
        :param newtype: the new type to replace
        '''
        if hasattr(name, 'readablename'):
            name = name.readablename
        t,i = self._target._embedded_indices[name]
        t._seqs[i] = newtype.parser().new(self._target)
    def _get_embedded(self, name):
        '''
        Return an embedded struct object to calculate the size or use _tobytes(True) to convert just the
        embedded parts.
        
        :param name: either the original type, or the name of the original type. It is always the type
                     used in type definitions, even if it is already replaced once or more.
        
        :returns: an embedded struct
        '''
        if hasattr(name, 'readablename'):
            name = name.readablename
        t,i = self._target._embedded_indices[name]
        return t._seqs[i]        
    @staticmethod
    def _registerPickleType(name, typedef):
        '''
        Register a type with the specified name. After registration, NamedStruct with this type
        (and any sub-types) can be successfully pickled and transfered.
        '''
        NamedStruct._pickleNames[typedef] = name
        NamedStruct._pickleTypes[name] = typedef

class EmbeddedStruct(NamedStruct):
    def __init__(self, parser, inlineparent):
        NamedStruct.__init__(self, parser)
        _set(self, '_target', inlineparent)
    def _create_embedded_indices(self):
        '''
        Create indices for all the embedded structs. For parser internal use.
        '''
        try:
            self._target._embedded_indices.update(((k,(self,v)) for k,v in getattr(self._parser.typedef, 'inline_names', {}).items()))
        except AttributeError:
            pass
    def __getattr__(self, name):
        '''
        Get attribute value from NamedStruct.
        '''
        if name[:1] != '_':
            return getattr(self._target, name)
        else:
            raise AttributeError('%r is not defined' % (name,))
    def __setattr__(self, name, value):
        if name[:1] != '_':
            setattr(self._target, name, value)
        else:
            object.__setattr__(self, name, value)
    def __delattr__(self, name):
        if name[:1] != '_':
            delattr(self._target, name)
        else:
            object.__delattr__(self, name)
        

def _create_struct(parser, inlineparent = None):
    if inlineparent is None:
        r = NamedStruct(parser)
    else:
        r = EmbeddedStruct(parser, inlineparent)
    r._create_embedded_indices()
    return r
    
DUMPTYPE_FLAT = 'flat'
DUMPTYPE_KEY = 'key'
DUMPTYPE_NONE = 'none'


def _to_str(dumped_val, encoding='utf-8', ordered=True):
    """
    Convert bytes in a dump value to str, allowing json encode
    """
    _dict = OrderedDict if ordered else dict
    if isinstance(dumped_val, dict):
        return OrderedDict((k, _to_str(v, encoding)) for k,v in dumped_val.items())
    elif isinstance(dumped_val, (list, tuple)):
        return [_to_str(v, encoding) for v in dumped_val]
    elif isinstance(dumped_val, bytes):
        try:
            d = dumped_val.decode('utf-8')
        except Exception:
            d = repr(dumped_val)
        return d
    else:
        return dumped_val


def dump(val, humanread = True, dumpextra = False, typeinfo = DUMPTYPE_FLAT, ordered=True,
         tostr=False, encoding='utf-8'):
    '''
    Convert a parsed NamedStruct (probably with additional NamedStruct as fields) into a
    JSON-friendly format, with only Python primitives (dictionaries, lists, bytes, integers etc.)
    Then you may use json.dumps, or pprint to further process the result.
    
    :param val: parsed result, may contain NamedStruct
    
    :param humanread: if True (default), convert raw data into readable format with type-defined formatters.
            For example, enumerators are converted into names, IP addresses are converted into dotted formats, etc.
             
    :param dumpextra: if True, dump "extra" data in '_extra' field. False (default) to ignore them.
    
    :param typeinfo: Add struct type information in the dump result. May be the following values:
    
      DUMPTYPE_FLAT ('flat')
        add a field '_type' for the type information (default)
      
      DUMPTYPE_KEY ('key')
        convert the value to dictionary like: {'<struc_type>': value}
      
      DUMPTYPE_NONE ('none')
        do not add type information
    
    :param tostr: if True, convert all bytes to str
    
    :param encoding: if tostr=`True`, first try to decode bytes in `encoding`. If failed, use `repr()` instead.
    
    :returns: "dump" format of val, suitable for JSON-encode or print.
    '''
    dumped = _dump(val, humanread, dumpextra, typeinfo, ordered)
    if tostr:
        dumped = _to_str(dumped, encoding, ordered)
    return dumped


def _dump(val, humanread = True, dumpextra = False, typeinfo = DUMPTYPE_FLAT, ordered=True):
    if val is None:
        return val
    if isinstance(val, NamedStruct):
        t = val._gettype()
        if t is None:
            r = dict((k, _dump(v, humanread, dumpextra, typeinfo)) for k, v in val.__dict__.items() if not k[:1] != '_')
        else:
            if humanread:
                r = dict((k, _dump(v, humanread, dumpextra, typeinfo)) for k, v in val.__dict__.items() if k[:1] != '_')
                if ordered:
                    r = t.reorderdump(r, val)
                r = t.formatdump(r, val)
                if hasattr(t, 'extraformatter'):
                    try:
                        r = t.extraformatter(r)
                    except:
                        NamedStruct._logger.log(logging.DEBUG, 'A formatter thrown an exception', exc_info = True)
            else:
                r = dict((k, _dump(v, humanread, dumpextra, typeinfo)) for k, v in val.__dict__.items() if k[:1] != '_')
                if ordered:
                    r = t.reorderdump(r, val)
        if dumpextra:
            extra = val._getextra()
            if extra:
                try:
                    r['_extra'] = extra
                except:
                    pass
        if t is not None:
            if typeinfo == DUMPTYPE_FLAT:
                try:
                    r['_type'] = '<' + repr(t) + '>'
                except:
                    pass
            elif typeinfo == DUMPTYPE_KEY:
                r = {'<' + repr(t) + '>' : r}
        return r
    elif isinstance(val, InlineStruct):
        return dict((k, _dump(v, humanread, dumpextra, typeinfo)) for k, v in val.__dict__.items() if k[:1] != '_')
    elif isinstance(val, list) or isinstance(val, tuple):
        return [_dump(v, humanread, dumpextra, typeinfo) for v in val]
    else:
        return val


def _copy(buffer):
    try:
        if isinstance(buffer, memoryview):
            return buffer.tobytes()
        else:
            return buffer[:]
    except:
        return buffer[:]

def sizefromlen(limit, *properties):
    '''
    Factory to generate a function which get size from specified field with limits.
    Often used in nstruct "size" parameter.
    
    To retrieve size without limit, simply use lambda expression: lambda x: x.header.length
    
    :param limit: the maximum size limit, if the acquired value if larger then the limit, BadLenError is raised
            to protect against serious result like memory overflow or dead loop.
            
    :param properties: the name of the specified fields. Specify more than one string to form a property path,
            like: sizefromlen(256, 'header', 'length') -> s.header.length
            
    :returns: a function which takes a NamedStruct as parameter, and returns the length value from specified
            property path.
    '''
    def func(namedstruct):
        v = namedstruct._target
        for p in properties:
            v = getattr(v, p)
        if v > limit:
            raise BadLenError('Struct length exceeds limit ' + str(limit))
        return v
    return func

def packsize(*properties):
    '''
    Revert to sizefromlen, store the struct size (len(struct)) to specified property path. The size includes
    padding. To store the size without padding, use packrealsize() instead. Often used in nstruct "prepack"
    parameter.
    
    :param properties: specified field name, same as sizefromlen.
    
    :returns: a function which takes a NamedStruct as parameter, and pack the size to specified field.
    
    '''
    def func(namedstruct):
        v = namedstruct._target
        for p in properties[:-1]:
            v = getattr(v, p)
        setattr(v, properties[-1], len(namedstruct))
    return func

def packrealsize(*properties):
    '''
    Revert to sizefromlen, pack the struct real size (struct._realsize()) to specified property path.
    Unlike packsize, the size without padding is stored. Often used in nstruct "prepack" parameter.
    
    :param properties: specified field name, same as sizefromlen.
    
    :returns: a function which takes a NamedStruct as parameter, and pack the size to specified field.
    
    '''
    def func(namedstruct):
        v = namedstruct._target
        for p in properties[:-1]:
            v = getattr(v, p)
        setattr(v, properties[-1], namedstruct._realsize())
    return func

def packvalue(value, *properties):
    '''
    Store a specified value to specified property path. Often used in nstruct "init" parameter.
    
    :param value: a fixed value
    
    :param properties: specified field name, same as sizefromlen.
    
    :returns: a function which takes a NamedStruct as parameter, and store the value to property path.
    
    '''
    def func(namedstruct):
        v = namedstruct._target
        for p in properties[:-1]:
            v = getattr(v, p)
        setattr(v, properties[-1], value)
    return func

def packexpr(func, *properties):
    '''
    Store a evaluated value to specified property path. Often used in nstruct "prepack" parameter.
    
    :param func: a function which takes a NamedStruct as parameter and returns a value, often a lambda expression
    
    :param properties: specified field name, same as sizefromlen.
    
    :returns: a function which takes a NamedStruct as parameter, and store the return value of func to property path.
    '''
    def func2(namedstruct):
        v = namedstruct._target
        for p in properties[:-1]:
            v = getattr(v, p)
        setattr(v, properties[-1], func(namedstruct))
    return func2

class InlineStruct(object):
    '''
    Just a storage object. Sometimes a struct definition maybe "inlined" to improve performance, this
    object stands for a inlined struct.
    '''
    def __init__(self, parent):
        self._parent = parent
    def __repr__(self, *args, **kwargs):
        return repr(dict((k,v) for k,v in self.__dict__.items() if k[:1] != '_'))


def _never(namedstruct):
    return False

class Parser(object):
    '''
    Base class for many struct parsers (not every though). End user should not call interfaces of a parser.
    Call interfaces of the typedef instead.
    '''
    logger = logging.getLogger(__name__ + '.Parser')
    def __init__(self, base = None, criteria = _never, padding = 8, initfunc = None, typedef = None, classifier = None, classifyby = None,
                 prepackfunc = None):
        '''
        Parser base class initializer.
        
        :param base: if specified, this parser sub-classes an existing type.
        
        :param criteria: sub-classing criteria. If matched, the base class can be sub-classed into this type.
        
        :param padding: padding this struct to align to padding-bytes boundaries. Specify 1 for no alignment.
        
        :param initfunc: initializer of the struct type when a new instance is created.
        
        :param typedef: the type definition of this parser.
        
        :param classifier: if specified, a special value is calculated on this struct, and the sub-class type is
                determined by this value, instead of using "criteria". This is defined on the base class.
                
        :param classifyby: if specified and the base class has a "classifier", when the calucated "classify" value
                is in classifyby, the base class can be sub-classed into this type.
                
        :param prepack: function executed before packing
        '''
        self.subclasses = []
        self.subindices = {}
        self.base = base
        self.padding = padding
        self.isinstance = criteria
        self.initfunc = initfunc
        self.typedef = typedef
        self.classifier = classifier
        self.prepackfunc = prepackfunc
        if self.base is not None:
            self.base.subclasses.append(self)
            if classifyby is not None:
                for v in classifyby:
                    self.base.subindices[v] = self
    def parse(self, buffer, inlineparent = None):
        '''
        Try to parse the struct from bytes sequence. The bytes sequence is taken from a streaming source.
        :param buffer: bytes sequence to be parsed from.
        :param inlineparent: if specified, this struct is embedded in another struct.
        :returns: None if the buffer does not have enough data for this struct (e.g. incomplete read
                from socket); (struct, size) else, where struct is the parsed result (usually a NamedStruct object)
                and size is the used bytes length, so you can start another parse from buffer[size:].
        '''
        if self.base is not None:
            return self.base.parse(buffer, inlineparent)
        r = self._parse(buffer, inlineparent)
        if r is None:
            return None
        (s, size) = r
        self.subclass(s)
        return (s, (size + self.padding - 1) // self.padding * self.padding)
    def subclass(self, namedstruct):
        '''
        Sub-class a NamedStruct into correct sub types.
        :param namedstruct: a NamedStruct of this type.
        '''
        cp = self
        cs = namedstruct
        while True:
            if hasattr(cs, '_sub'):
                cs = cs._sub
                cp = cs._parser
                continue
            subp = None
            clsfr = getattr(cp, 'classifier', None)
            if clsfr is not None:
                clsvalue = clsfr(namedstruct)
                subp = cp.subindices.get(clsvalue)
            if subp is None:
                for sc in cp.subclasses:
                    if sc.isinstance(namedstruct):
                        subp = sc
                        break
            if subp is None:
                break
            cs._subclass(subp)
            cs = cs._sub
            cp = subp
    def _parse(self, buffer, inlineparent):
        '''
        Internal interface to parse from some data. Different from parse(), this interface returns "real" size
        (without padding), and does not sub-class the struct.
        :param buffer: data to parse from.
        :param inlineparent: if specified, this struct is embedded in another struct.
        :returns: None if the buffer does not have enough data for this struct (e.g. incomplete read
                from socket); (struct, size) else, where struct is the parsed result (usually a NamedStruct object)
                and size is the REAL SIZE of the struct.
        '''
        raise NotImplementedError
    def new(self, inlineparent = None):
        '''
        Create an empty struct of this type. "initfunc" is called on the created struct to initialize it.
        :param inlineparent: if specified, this struct is embedded into another struct "inlineparent"
        :returns: a created struct (usually a NamedStruct object)
        '''
        if self.base is not None:
            s = self.base.new(inlineparent)
            s._extend(self._new(s._target))
        else:
            s = self._new(inlineparent)
        if self.initfunc is not None:
            self.initfunc(s)
        return s
    def _new(self, inlineparent = None):
        '''
        Internal interface for new.
        '''
        raise NotImplementedError
    def _create(self, data, inlineparent = None):
        c = _create_struct(self, inlineparent)
        c._unpack(data)
        return c
    def create(self, data, inlineparent = None):
        '''
        Create a struct and use all bytes of data. Different from parse(), this takes all data,
        store unused bytes in "extra" data of the struct. Some types like variable-length array
        may have different parse result with create() and parse().
        :param data: bytes of a packed struct.
        :param inlineparent: if specified, this struct is embedded in another struct "inlineparent"
        :returns: a created NamedStruct object.
        '''
        if self.base is not None:
            return self.base.create(data, inlineparent)
        c = self._create(data, inlineparent)
        self.subclass(c)
        return c
    def paddingsize(self, namedstruct):
        '''
        Return the size of the padded struct (including the "real" size and the padding bytes)
        :param namedstruct: a NamedStruct object of this type.
        :returns: size including both data and padding.
        '''
        realsize = namedstruct._realsize()
        return (realsize + self.padding - 1) // self.padding * self.padding
    def paddingsize2(self, realsize):
        '''
        Return a padded size from realsize, for NamedStruct internal use.
        '''
        return (realsize + self.padding - 1) // self.padding * self.padding
    def tobytes(self, namedstruct, skipprepack = False):
        '''
        Convert a NamedStruct to packed bytes.
        
        :param namedstruct: a NamedStruct object of this type to pack.
        
        :param skipprepack: if True, the prepack stage is skipped.
        
        :returns: packed bytes
        '''
        return namedstruct._tobytes(skipprepack)
    def prepack(self, namedstruct):
        '''
        Run prepack
        '''
        if self.prepackfunc is not None:
            self.prepackfunc(namedstruct)

class FormatParser(Parser):
    '''
    Parsing or serializing a NamedStruct with format specified with "struct" library format.
    There is no need to create the parser yourself. "nstruct" creates the correct type and parser for you.
    FormatParser parses a struct with only fields of primitive types, or fix-size arrays of primitive types.
    Some struct definitions with very small structs may also form this type of struct after "inline".
    This is the most basic type of parsing.
    '''
    def __init__(self, fmt, properties, sizefunc = None, prepackfunc = None, base = None, criteria = _never, padding = 8, endian = '>', initfunc = None, typedef = None, classifier = None, classifyby = None):
        '''
        Initializer.
        :param fmt: a struct format string, without endian specifier. (e.g. 'IBB4sQ')
        :param properties: property definitions.
        :param sizefunc: function to retrieve struct size.
        :param prepackfunc: function to be executed before pack.
        :param base: base type of this parser.
        :param criteria: see Parser.__init__
        :param padding: see Parser.__init__
        :param endian: endian specifier, default to '>' (Big endian, or network order)
        :param initfunc: see Parser.__init__
        :param typedef: see Parser.__init__
        :param classifier: see Parser.__init__
        :param classifyby: see Parser.__init__
        '''
        Parser.__init__(self, base, criteria, padding, initfunc, typedef, classifier, classifyby, prepackfunc)
        self.struct = struct.Struct(endian + fmt)
        self.properties = properties
        self.emptydata = b'\x00' * self.struct.size
        self.sizefunc = sizefunc
    def _parse(self, buffer, inlineparent = None):
        if len(buffer) < self.struct.size:
            return None
        s = _create_struct(self, inlineparent)
        self.unpack(buffer[0:self.struct.size], s)
        if self.sizefunc is not None:
            size = self.sizefunc(s)
            if size < self.struct.size:
                raise BadFormatError('struct size should be greater than %d bytes, got %d' % (self.struct.size, size))
            if len(buffer) < size:
                return None
            _set(s, '_extra', _copy(buffer[self.struct.size:size]))
        else:
            _set(s, '_extra', b'')
            size = self.struct.size
        return (s, size)
    def _new(self, inlineparent = None):
        s = _create_struct(self, inlineparent)
        s._unpack(self.emptydata)
        return s
    def sizeof(self, namedstruct):
        '''
        Return the "real" size of the struct.
        '''
        return self.struct.size
    def unpack(self, data, namedstruct):
        '''
        Unpack the struct from specified bytes. If the struct is sub-classed, definitions from the sub type
        is not unpacked.
        :param data: bytes of the struct, including fields of sub type and "extra" data.
        :param namedstruct: a NamedStruct object of this type
        :returns: unused bytes from data, which forms data of the sub type and "extra" data. 
        '''
        try:
            result = self.struct.unpack(data[0:self.struct.size])
        except struct.error as exc:
            raise BadFormatError(exc)
        start = 0
        t = namedstruct._target
        for p in self.properties:
            if len(p) > 1:
                if isinstance(result[start], bytes):
                    v = [r.rstrip(b'\x00') for r in result[start:start + p[1]]]
                else:
                    v = list(result[start:start + p[1]])
                start += p[1]
            else:
                v = result[start]
                if isinstance(v, bytes):
                    v = v.rstrip(b'\x00')
                start += 1
            setin = t
            for sp in p[0][0:-1]:
                if not hasattr(setin, sp):
                    setin2 = InlineStruct(namedstruct._target)
                    setattr(setin, sp, setin2)
                    setin = setin2
                else:
                    setin = getattr(setin, sp)
            setattr(setin, p[0][-1], v)
        return data[self.struct.size:]
    def pack(self, namedstruct):
        '''
        Pack the struct and return the packed bytes.
        :param namedstruct: a NamedStruct of this type.
        :returns: packed bytes, only contains fields of definitions in this type, not the sub type and "extra" data.
        '''
        elements = []
        t = namedstruct._target
        for p in self.properties:
            v = t
            for sp in p[0]:
                v = getattr(v, sp)
            if len(p) > 1:
                elements.extend(v[0:p[1]])
            else:
                elements.append(v)
        return self.struct.pack(*elements)

class SequencedParser(Parser):
    '''
    A parser constructed by a sequence of parsers. nstruct() automatically creates this kind of parser if necessary.
    This kind of parser uses other parsers (including other sequenced parsers) to parse fields.
    '''
    def __init__(self, parserseq, sizefunc = None, prepackfunc = None, lastextra = True, base = None, criteria = _never, padding = 8, initfunc = None, typedef = None, classifier = None, classifyby = None):
        '''
        Initializer.
        :param parserseq: parser sequence definitions.
        :param sizefunc: function to retrieve struct size.
        :param prepackfunc: function to be executed before pack.
        :param lastextra: if True, the last field of this type will use all the available bytes, instead of
                leaving them to sub type or "extra" data. If False, additional data is preserved for sub type and
                "extra" data even if the last field can take more.
        :param base: base type of this parser
        :param criteria: see Parser.__init__
        :param padding: see Parser.__init__
        :param initfunc: see Parser.__init__
        :param typedef: see Parser.__init__
        :param classifier: see Parser.__init__
        :param classifyby: see Parser.__init__
        '''
        Parser.__init__(self, base, criteria, padding, initfunc, typedef, classifier, classifyby, prepackfunc)
        self.parserseq = parserseq
        self.sizefunc = sizefunc
        if lastextra:
            self.parserseq = parserseq[0:-1]
            self.extra = parserseq[-1]
    def _parse(self, buffer, inlineparent = None):
        s = _create_struct(self, inlineparent)
        size = self._parseinner(buffer, s, True, False)
        if size is None:
            return None
        else:
            return (s, size)
    def _parseinner(self, buffer, namedstruct, copy = False, useall = True):
        s = namedstruct
        inlineparent = s._target
        s._seqs = []
        start = 0
        for p, name in self.parserseq:
            parent = None
            if name is None:
                parent = inlineparent
            if name is not None and len(name) > 1:
                # Array
                v = []
                for _ in range(0, name[1]):
                    r = p.parse(buffer[start:], parent)
                    if r is None:
                        return None
                    v.append(r[0])
                    start += r[1]
                setattr(inlineparent, name[0], v)
            else:
                r = p.parse(buffer[start:], parent)
                if r is None:
                    return None
                (s2, size) = r
                if name is not None:
                    setattr(inlineparent, name[0], s2)
                else:
                    s._seqs.append(s2)
                start += size
        if useall:
            size = len(buffer)
        else:
            if self.sizefunc is not None:
                size = self.sizefunc(s)
                if size < start:
                    raise BadFormatError('struct size should be greater than %d bytes, got %d' % (start, size))
            else:
                size = start
        if hasattr(self, 'extra'):
            p, name = self.extra
            if name is not None and len(name) > 1:
                extraArray = []
                while start < size:
                    r = p.parse(buffer[start:size], None)
                    if r is None:
                        break
                    extraArray.append(r[0])
                    start += r[1]
                setattr(inlineparent, name[0], extraArray)
            else:
                if name is None:
                    s2 = p.create(buffer[start:size], inlineparent)
                    s._seqs.append(s2)
                else:
                    setattr(inlineparent, name[0], p.create(buffer[start:size], None))
        else:
            _set(s, '_extra', _copy(buffer[start:size]))
        return size
    def unpack(self, data, namedstruct):
        size = self._parseinner(data, namedstruct, False, True)
        if size is None:
            raise BadLenError('Cannot parse struct: data is corrupted.')
        try:
            extra = getattr(namedstruct, '_extra')
            del namedstruct._extra
            return extra
        except:
            return b''
    def pack(self, namedstruct):
        packdata = []
        s = namedstruct
        inlineparent = s._target
        seqiter = iter(s._seqs)
        for p, name in self.parserseq:
            if name is not None and len(name) > 1:
                # Array
                v = getattr(inlineparent, name[0])
                for i in range(0, name[1]):
                    if i >= len(v):
                        packdata.append(p.tobytes(p.new()))
                    else:
                        packdata.append(p.tobytes(v[i]))
            else:
                if name is not None:
                    v = getattr(inlineparent, name[0])
                    packdata.append(p.tobytes(v))
                else:
                    v = next(seqiter)
                    packdata.append(p.tobytes(v, True))
        if hasattr(self, 'extra'):
            p, name = self.extra
            if name is not None and len(name) > 1:
                v = getattr(inlineparent, name[0])
                for es in v:
                    packdata.append(p.tobytes(es))
            else:
                if name is None:
                    v = next(seqiter)
                    packdata.append(p.tobytes(v, True))
                else:
                    v = getattr(inlineparent, name[0])
                    packdata.append(p.tobytes(v))
        return b''.join(packdata)
    def _new(self, inlineparent = None):
        s = _create_struct(self, inlineparent)
        inlineparent = s._target
        s._seqs = []
        for p, name in self.parserseq:
            if name is not None and len(name) > 1:
                # Array
                v = [p.new() for _ in range(0, name[1])]
                setattr(inlineparent, name[0], v)
            else:
                if name is not None:
                    v = p.new()
                    setattr(inlineparent, name[0], v)
                else:
                    v = p.new(inlineparent)
                    s._seqs.append(v)
        if hasattr(self, 'extra'):
            p, name = self.extra
            if name is not None and len(name) > 1:
                setattr(inlineparent, name[0], [])
            else:
                if name is None:
                    s2 = p.new(inlineparent)
                    s._seqs.append(s2)
                else:
                    setattr(inlineparent, name[0], p.new())
        else:
            s._extra = b''
        return s
    def sizeof(self, namedstruct):
        size = 0
        s = namedstruct
        inlineparent = s._target
        seqiter = iter(s._seqs)
        for p, name in self.parserseq:
            if name is not None and len(name) > 1:
                # Array
                v = getattr(inlineparent, name[0])
                for i in range(0, name[1]):
                    if i >= len(v):
                        size += p.paddingsize(p.new())
                    else:
                        size += p.paddingsize(v[i])
            else:
                if name is not None:
                    v = getattr(inlineparent, name[0])
                else:
                    v = next(seqiter)
                size += p.paddingsize(v)
        if hasattr(self, 'extra'):
            p, name = self.extra
            if name is not None and len(name) > 1:
                v = getattr(inlineparent, name[0])
                for es in v:
                    size += p.paddingsize(es)
            else:
                if name is None:
                    v = next(seqiter)
                else:
                    v = getattr(inlineparent, name[0])
                size += p.paddingsize(v)
        return size
    def prepack(self, namedstruct):
        for s in namedstruct._seqs:
            if hasattr(s, '_prepack'):
                s._prepack()
        Parser.prepack(self, namedstruct)

class PrimitiveParser(object):
    '''
    Parser to parse a primitive type, usually returns Python primitive types like bytes or integers.
    prim() type creates this kind of parser, if it cannot be "inlined".
    A primitive type is never sub-classed, and can not have padding bytes.
    '''
    def __init__(self, fmt, endian = '>'):
        '''
        :param fmt: struct format string of a primitive type without endian specifier (e.g. 'I')
        :param endian: endian specifier, default to '>'
        '''
        self.struct = struct.Struct(endian + fmt)
        self.emptydata = b'\x00' * self.struct.size
        self.empty = self.struct.unpack(self.emptydata)[0]
        if isinstance(self.empty, bytes):
            self.empty = b''
    def parse(self, buffer, inlineparent = None):
        '''
        Compatible to Parser.parse()
        '''
        if len(buffer) < self.struct.size:
            return None
        try:
            return (self.struct.unpack(buffer[:self.struct.size])[0], self.struct.size)
        except struct.error as exc:
            raise BadFormatError(exc)
    def new(self, inlineparent = None):
        '''
        Compatible to Parser.new()
        '''
        return self.empty
    def create(self, data, inlineparent = None):
        '''
        Compatible to Parser.create()
        '''
        try:
            return self.struct.unpack(data)[0]
        except struct.error as exc:
            raise BadFormatError(exc)
    def sizeof(self, prim):
        '''
        Compatible to Parser.sizeof()
        '''
        return self.struct.size
    def paddingsize(self, prim):
        '''
        Compatible to Parser.paddingsize()
        '''
        return self.struct.size
    def tobytes(self, prim, skipprepack = False):
        '''
        Compatible to Parser.tobytes()
        '''
        return self.struct.pack(prim)

class ArrayParser(object):
    '''
    Fixed or variable length array parser. Array type cannot be sub-classed or padded.
    '''
    def __init__(self, innerparser, size):
        '''
        Initializer.
        :param innerparser: inner type parser.
        :param size: array size. 0 for variable size array.
        '''
        self.innerparser = innerparser
        self.size = size
    def parse(self, buffer, inlineparent = None):
        '''
        Compatible to Parser.parse()
        '''
        size = 0
        v = []
        for i in range(0, self.size):  # @UnusedVariable
            r = self.innerparser.parse(buffer[size:], None)
            if r is None:
                return None
            v.append(r[0])
            size += r[1]
        return (v, size)
    def new(self, inlineparent = None):
        '''
        Compatible to Parser.new()
        '''
        v = list(range(0, self.size))
        for i in range(0, self.size):
            v[i] = self.innerparser.new()
        return v
    def create(self, data, inlineparent = None):
        '''
        Compatible to Parser.create()
        '''
        if self.size > 0:
            r = self.parse(data)
            if r is None:
                raise ParseError('data is not enough to create an array of size ' + self.size)
            else:
                return r[0]
        else:
            v = []
            start = 0
            while start < len(data):
                r = self.innerparser.parse(data[start:], None)
                if r is None:
                    break
                v.append(r[0])
                start += r[1]
            return v
    def sizeof(self, prim):
        '''
        Compatible to Parser.sizeof()
        '''
        size = 0
        arraysize = self.size
        if arraysize == 0:
            arraysize = len(prim)
        for i in range(0, arraysize):
            if i >= len(prim):
                size += self.innerparser.paddingsize(self.innerparser.new())
            else:
                size += self.innerparser.paddingsize(prim[i])
        return size
    def paddingsize(self, prim):
        '''
        Compatible to Parser.paddingsize()
        '''
        return self.sizeof(prim)
    def tobytes(self, prim, skipprepack = False):
        '''
        Compatible to Parser.tobytes()
        '''
        data = []
        arraysize = self.size
        if arraysize == 0:
            arraysize = len(prim)
        for i in range(0, arraysize):
            if i >= len(prim):
                data.append(self.innerparser.tobytes(self.innerparser.new()))
            else:
                data.append(self.innerparser.tobytes(prim[i]))
        return b''.join(data)
        


class RawParser(object):
    '''
    Parser for variable length bytes.
    '''
    def __init__(self, cstr = False):
        '''
        :param cstr: if True, the '\x00' bytes are stripped from end of the data, like C-string.
        '''
        self.cstr = cstr
    def parse(self, buffer, inlineparent = None):
        '''
        Compatible to Parser.parse()
        '''
        return (b'', 0)
    def new(self, inlineparent = None):
        '''
        Compatible to Parser.new()
        '''
        return b''
    def create(self, data, inlineparent = None):
        '''
        Compatible to Parser.create()
        '''
        if self.cstr:
            return data.rstrip(b'\x00')
        else:
            return data
    def sizeof(self, prim):
        '''
        Compatible to Parser.sizeof()
        '''
        return len(prim)
    def paddingsize(self, prim):
        '''
        Compatible to Parser.paddingsize()
        '''
        return len(prim)
    def tobytes(self, prim, skipprepack = False):
        '''
        Compatible to Parser.tobytes()
        '''
        return prim

class CstrParser(object):
    '''
    A zero-ended C-style string (bytes). Different from raw(True), the length of the bytes is determined by
    the ending zero ('\x00'), and the ending zero cannot be omitted. The parsed bytes does not include the
    ending zero byte.
    '''
    def __init__(self):
        pass
    def parse(self, buffer, inlineparent = None):
        for i in range(0, len(buffer)):
            if buffer[i:i+1] == b'\x00':
                return (buffer[0:i], i + 1)
        return None
    def new(self, inlineparent = None):
        return b''
    def create(self, data, inlineparent = None):
        if data[-1:] != b'\x00':
            raise BadFormatError(b'Cstr is not zero-terminated')
        for i in range(0, len(data) - 1):
            if data[i:i+1] == b'\x00':
                raise BadFormatError(b'Cstr has zero inside the string')
        return data
    def sizeof(self, prim):
        return len(prim) + 1
    def paddingsize(self, prim):
        return self.sizeof(prim)
    def tobytes(self, prim, skipprepack = False):
        return prim + b'\x00'

class typedef(object):
    '''
    Base class for type definitions. Types defined with *nstruct*, *prim*, *optional*, *bitfield*
    all have these interfaces.
    '''
    def parser(self):
        '''
        Get parser for this type. Create the parser on first call.
        '''
        if not hasattr(self, '_parser'):
            self._parser = self._compile()
        return self._parser
    def parse(self, buffer):
        '''
        Parse the type from specified bytes stream, and return the first one if exists.
        
        :param buffer: bytes from a stream, may contains only part of the struct, exactly one struct, or
                additional bytes after the struct.
                       
        :returns: None if the data is incomplete; (data, size) else, where data is the parsed data, size is
                  the used bytes length, so the next struct begins from buffer[size:]
        '''
        return self.parser().parse(buffer)
    def create(self, buffer):
        '''
        Create a object from all the bytes. If there are additional bytes, they may be fed greedily to
        a variable length type, or may be used as "extra" data.
        :param buffer: bytes of a packed struct.
        :returns: an object with exactly the same bytes when packed.
        :raises: BadFormatError or BadLenError if the bytes cannot completely form this type.
        '''
        d = self.parser().create(buffer)
        return d
    def new(self, *args, **kwargs):
        '''
        Create a new object of this type. It is also available as __call__, so you can create a new object
        just like creating a class instance: a = mytype(a=1,b=2)
        
        :param args: Replace the embedded struct type. Each argument is a tuple (name, newtype).
                     It is equivalent to call _replace_embedded_type with *name* and *newtype*
                     one by one. Both the "directly" embedded struct and the embedded struct inside another
                     embedded struct can be set. If you want to replace an embedded struct in a
                     replaced struct type, make sure the outer struct is replaced first. The embeded
                     struct type must have a *name* to be replaced by specify *name* option.
                       
        :param kwargs: extra key-value arguments, each one will be set on the new object, to set value
                       to the fields conveniently.
        
        :returns: a new object, with the specified "kwargs" set.
        '''
        obj = self.parser().new()
        for k,v in args:
            obj._replace_embedded_type(k,v)
        for k,v in kwargs.items():
            setattr(obj, k, v)
        return obj
    def __call__(self, *args, **kwargs):
        '''
        Same as new()
        '''
        return self.new(*args, **kwargs)
    def tobytes(self, obj):
        '''
        Convert the object to packed bytes. If the object is a NamedStruct, it is usually obj._tobytes();
        but it is not possible to call _tobytes() for primitive types.
        '''
        return self.parser().tobytes(obj)
    def inline(self):
        '''
        Returns whether this type can be "inlined" into other types. If the type is inlined into other types,
        it is splitted and re-arranged to form a FormatParser to improve performance.
        If not, the parser is used instead.
        :returns: None if this type cannot be inlined; a format definition similar to FormatParser if it can.
        '''
        return None
    def array(self, size):
        '''
        Create an array type, with elements of this type. Also available as indexer([]), so
        mytype[12] creates a array with fixed size 12; mytype[0] creates a variable size array.
        :param size: the size of the array, 0 for variable size array.
        '''
        return arraytype(self, size)
    def vararray(self):
        '''
        Same as array(0)
        '''
        return self.array(0)
    def __getitem__(self, size):
        '''
        Same as array(size), make it similar to C/Java type array definitions.
        It is worth to notice that the array is in column order, unlike in C.
        For example, uint16[3][4] is a list with 4 elements, each is a list
        of 3 uint16. uint16[5][0] is a variable length array, whose elements
        are lists of 5 uint16.
        '''
        return self.array(size)
    def isextra(self):
        '''
        Returns whether this type can take extra data. For example, a variable size array
        will be empty when parsed, but will have elements when fed with extra data (like 
        when create() is called)
        '''
        return False
    def formatdump(self, dumpvalue, v):
        '''
        Format the dumpvalue when dump() is called with humanread = True
        
        :param dumpvalue: the return value of dump() before formatting.
        
        :param v: the original data
        
        :returns: return a formatted version of the value.
        
        '''
        return dumpvalue
    def reorderdump(self, dumpvalue, v):
        '''
        Reorder the dict to match the original field order
        '''
        return dumpvalue

class arraytype(typedef):
    '''
    Array of some other type. The parsed result will be a list of elements.
    '''
    def __init__(self, innertype, size = 0):
        '''
        :param innertype: type of elements.
        :param size: size of the array, 0 for variable size array, >0 for fixed size array.
        '''
        self.innertype = innertype
        self.size = size
    def _compile(self):
        '''
        Create parser
        '''
        return ArrayParser(self.innertype.parser(), self.size)
    def isextra(self):        
        return self.size == 0
    def array(self, size):
        if self.size == 0:
            raise TypeError('variable length array cannot form array')
        else:
            return typedef.array(self, size)
    def __repr__(self, *args, **kwargs):
        return '%r[%d]' % (self.innertype, self.size)

class rawtype(typedef):
    '''
    Raw bytes with variable size. The parsed result is bytes.
    '''
    _parser = RawParser()
    def parser(self):
        return self._parser
    def array(self, size):
        raise TypeError('rawtype cannot form array')
    def isextra(self):
        return True
    def __repr__(self, *args, **kwargs):
        return 'raw'

raw = rawtype()

class varchrtype(typedef):
    '''
    Raw bytes with possible extra padding zeros. When parsed, the padding zero bytes are stripped.
    The parsed result is bytes.
    '''
    _parser = RawParser(True)
    def parser(self):
        return self._parser
    def array(self, size):
        raise TypeError('varchrtype cannot form array')
    def isextra(self):
        return True
    def __repr__(self, *args, **kwargs):
        return 'varchr'

varchr = varchrtype()

class cstrtype(typedef):
    '''
    A C-style string (bytes) ends with exactly one zero byte. The string (bytes) length is determined by
    the zero byte, like strlen() in C library. The length of packed bytes is exactly 1 + len(val).
    Unlike raw and varchr, this is a fix-sized type (though the size is determined from data).
    The parsing result is bytes.
    '''
    _parser = CstrParser()
    def parser(self):
        return self._parser
    def __repr__(self, *args, **kwargs):
        return 'cstr'

cstr = cstrtype()

class prim(typedef):
    '''
    Basic data types from struct library. The parsing result is specified by the format string.
    '''
    def __init__(self, fmt, readablename = None, endian = '>', strict = False):
        '''
        :param fmt: a Python struct format string without endian specify, like 'I' or 'B'
        :param readablename: a human-readable name for this type, used in __repr__
        :param endian: specify endian with struct format, default to '>' ("big endian" or "network order")
                use '<' for little endian; do not use ''.
        :param strict: disallow this type to be inlined. Only use strict = True if you want to
                use this type in structs with different endian (e.g. little endian integer in a big endian struct)
        '''
        typedef.__init__(self)
        self._format = fmt
        self._inline = (fmt, ())
        self._readablename = readablename
        self._endian = endian
        self._strict = strict
    def _compile(self):
        return PrimitiveParser(self._format, self._endian)
    def inline(self):
        if self._strict:
            return None
        else:
            return self._inline
    def __repr__(self, *args, **kwargs):
        if self._readablename is not None:
            return str(self._readablename)
        else:
            return ('prim(%r)' % (self.format,))

class chartype(prim):
    '''
    char type in C. Different with uint8, the array form(e.g. char[12]) returns a fix-length bytes
    type(prim('12s')), so the parsed result will be bytes, instead of list of integers/bytes.
    The parsed result is bytes of 1-length.
    '''
    def __init__(self):
        prim.__init__(self, 'c', 'char')
    def array(self, size):
        if size == 0:
            return raw
        else:
            return prim(str(size) + 's')

char = chartype()


def _merge_to(path, from_dict, to_dict):
    current = from_dict
    for p in path[:-1]:
        if p not in current:
            return
        current = current[p]
    if path[-1] not in current:
        return
    v = current.pop(path[-1])
    current = to_dict
    for p in path[:-1]:
        if p not in to_dict:
            to_dict[p] = OrderedDict()
        current = to_dict[p]
    current[path[-1]] = v


def _merge_dict(from_dict, to_dict):
    for k,v in from_dict.items():
        if isinstance(v, dict):
            _merge_dict(v, to_dict.setdefault(k, OrderedDict()))
        else:
            to_dict[k] = v


class fixedstruct(typedef):
    '''
    A type with fixed structure. Do not define this kind of type directly; nstruct will automatically create
    this kind of types to form a complete struct.
    The parsed result is a NamedStruct.
    '''
    def __init__(self, fmt, properties, sizefunc = None, prepackfunc = None, base = None, criteria = _never, padding = 8, endian = '>', readablename = None, inlineself = None, initfunc = None, nstructtype = None, classifier = None, classifyby = None):
        '''
        :param fmt: struct format string
        :param properties: field definitions
        :param sizefunc: function to retrieve struct size
        :param prepackfunc: function to be executed before struct pack
        :param base: base type of this type
        :param criteria: criteria of sub-class from base to this type
        :param padding: align the struct to padding-bytes boundaries
        :param endian: endian of this struct in struct format string, default to '>' (big endian)
        :param readablename: specify a human-readable name for this type, used in __repr__
        :param inlineself: True to allow "inline" this type into other types; False to disallow.
                If specify None, it is automatically determined from the structure size and other paramters.
        :param initfunc: function to be executed on new() (object creation), the "initializer"
        :param nstructtype: when a nstruct type is fully converted to a fixedstruct type, this parameter
                is provided to wrap this type as needed.
        :param classifier: if specified, a value is calculated by classifier(self) when sub-classing, to
                determine the sub type, instead of using criteria on every sub type.
        :param classifyby: a tuple, if specified and the parent type has a classifier, the base type will
                be sub-classed into this type if the calculated value of classifier is in this tuple.
        '''
        self.sizefunc = sizefunc
        self.prepackfunc = prepackfunc
        self.base = base
        self.criteria = criteria
        self.padding = padding
        self.endian = endian
        self.format = fmt
        self.properties = properties
        self.readablename = readablename
        self.initfunc = initfunc
        self.classifier = classifier
        self.classifyby = classifyby
        if nstructtype is None:
            nstructtype = self
        self.nstructtype = nstructtype
        size = struct.calcsize(endian + self.format)
        paddingsize = (size + padding - 1) // padding * padding
        if paddingsize > size:
            paddingformat = self.format + str(paddingsize - size) + 'x'
        else:
            paddingformat = self.format
        if inlineself is None:
            if self.base is None and self.sizefunc is None and self.prepackfunc is None and self.initfunc is None:
                self._inline = (paddingformat, self.properties)
            else:
                self._inline = None
        elif inlineself:
            self._inline = (paddingformat, self.properties)
        else:
            self._inline = None
    def _compile(self):
        return FormatParser(self.format, self.properties, self.sizefunc, self.prepackfunc, 
                            None if self.base is None else self.base.parser(), self.criteria, self.padding, self.endian,self.initfunc, self.nstructtype, self.classifier, self.classifyby)
    def inline(self):
        return self._inline
    def __repr__(self, *args, **kwargs):
        if self.readablename is not None:
            return str(self.readablename)
        else:
            return 'fixed(%r)' % (self.format,)
    def _reorder_properties(self, unordered_dict, ordered_dict, val):
        for p in self.properties:
            property_path = p[0]
            _merge_to(property_path, unordered_dict, ordered_dict)

class StructDefWarning(Warning):
    pass

class nstruct(typedef):
    '''
    Generic purpose struct definition. Struct is defined by fields and options, for example::
    
        mystruct = nstruct((uint32, 'a'),
                            (uint16[2], 'b'),
                            (mystruct2,'c'),
                            (uint8,),
                            (mystruct3,),
                            name = 'mystruct')
    
    uint32, uint16, uint8 are standard types from *stdprim*. uint16[2] creates an array type with
    fixed size of 2. Field names must be valid attribute names, and CANNOT begin with '_', because
    names begin with '_' is preserved for internal use.
    The defined struct is similar to C struct::
    
        typedef struct{
            int a;
            short b[2];
            struct mystruct2 c;
            char _padding;
            struct mystruct3;
        } mystruct;
    
    **A struct is in big-endian (network order) by default.** If you need a little-endian struct, specify *endian*
    option to '<' and use little-endian version of types at the same time::

        mystruct_le = nstruct((uint32_le, 'a'),
                            (uint16_le[2], 'b'),
                            (mystruct2_le,'c'),
                            (uint8_le,),
                            (mystruct3_le,),
                            name = 'mystruct_le',
                            endian = '<')
    
    Fields can be named or anonymous. Following rules are applied:
    - A named field parses a specified type and set the result to attribute with the specified name
    
    - A anonymous struct field embeds the struct into this struct: every attribute of the embedded struct
      can be accessed from the parent struct, and every attribute of parent struct can also be accessed
      from the embedded struct.
      
    - Any anonymous primitive types act as padding bytes, so there is not a specialized padding type
    
    - Anonymous array is not allowed.
    
    **Structs are aligned to 8-bytes (*padding* = 8) boundaries by default**, so if a struct defines fields of only 5 bytes,
    3 extra padding bytes are appended to the struct automatically. The struct is always padded to make
    the size multiplies of "padding" even if it contains complex sub-structs or arrays, so it is more
    convenient than adding padding bytes to definitions. For example, if a struct contains a variable array
    of 7-bytes size data type, you must add 1 byte when the variable array has only one element, and add 2 bytes
    when the variable array has two elements. The alignment (padding) can be adjusted with *padding* option.
    Specify 4 for 4-bytes (32-bit) alignment, 2 for 2-bytes (16-bit), etc. Specify 1 for 1-bytes alignment, 
    which equals to disable alignment.
    
    **Structs can hold more bytes than the size of defined fields.** A struct created with create() takes all
    the input bytes as part of the struct. The extra bytes are used in variable length data types, or stored
    as "extra" data to serve automatic sub-class.
    
    A variable length data type is a kind of data type whose size cannot be determined by itself. For example, a variable
    array can have 0 - infinite elements, and the actual size cannot be determined by the serialized bytes.
    If you merge multiple variable arrays into one bytes stream, the boundary of each array disappears. These
    kinds of data types usually can use as much data as possible. A struct contains a variable length data type
    as the last field type is also variable length. For example::
    
        varray = nstruct((uint16, 'length'),
                        (mystruct[0], 'structs'),
                        name = 'varray')
        
    When use parse() to parse from a bytes stream, the length of "structs" array is always 0, because parse()
    takes bytes only when they are ensured to be part of the struct. When use create() to create a struct from
    bytes, all the following bytes are parsed into "structs" array, which creates a array with correct length.
    
    Usually we want to be able to unpack the packed bytes and get exactly what are packed, so it is necessary to
    have a way to determine the struct size, for example, from the struct size stored in a field before the variable
    size part. Set *size* option to a function to retrieve the actual struct size::
        
        varray2 = nstruct((uint16, 'length'),
                          (mystruct[0], 'structs'),
                          name = 'varray2',
                          size = lambda x: x.length,
                          prepack = packrealsize('length')
                          )
    
    When this struct is parsed from a bytes stream, it is parsed in three steps:
    - A first parse to get the non-variable parts of the struct, just like what is done when *size* is not set
    
    - *size* function is called on the parsed result, and returns the struct size
    
    - A second parse is done with the correct size of data, like what is done with create()
    
    Usually the *size* function should return "real" size, which means size without the padding bytes at the end
    of struct, but it is usually OK to return the padded size. Variable length array ignores extra bytes which
    is not enough to form a array element. If the padding bytes are long enough to form a array element, the
    parsed result may contain extra empty elements and must be processed by user.
    
    The *prepack* option is a function which is executed just before pack, so the actual size is automatically
    stored to 'length' field. There is no need to care about the 'length' field manually. Other processes may
    also be done with *prepack* option.
    
    A struct without variable length fields can also have the *size* option to preserve data for extension.
    The bytes preserved are called "extra" data and stored in "_extra" attribute of the parsed result. You
    may use the "extra" data with _getextra() and _setextra() interface of the returned NamedStruct object.
    On packing, the "extra" data is appended directly after the last field, before the "padding" bytes, and
    counts for struct size, means the "extra" data is preserved in packing and unpacking::
        
        base1 = nstruct((uint16, 'length'),
                        (uint8, 'type'),
                        (uint8,),
                        name = 'base1',
                        size = lambda x: x.length,
                        prepack = packrealsize('length'))
    
    **The extra data can be used in sub-class.** A sub-classed struct is a struct begins with the base struct, and
    use the "extra" data of the base struct as the data of the extended fields. It works like the C++ class
    derive::
    
        child1 = nstruct((uint16, 'a1'),
                        (uint16, 'b1'),
                        base = base1,
                        criteria = lambda x: x.type == 1,
                        init = packvalue(1, 'type'),
                        name = 'child1')
        child2 = nstruct((uint8, 'a2'),
                        (uint32, 'b2'),
                        base = base1,
                        criteria = lambda x: x.type == 2,
                        init = packvalue(2, 'type'),
                        name = 'child2')
    
    A "child1" struct consists of a uint16 'length', a uint8 'type', a uint8 padding byte, a uint16 'a1', a uint16 'b1';
    the "child2" struct consists of a uint16 'length', a uint8 'type', a uint8 padding byte, a uint8 'a2', a uint32 'b2',
    and 7 padding bytes (to make the total size 16-bytes).
    
    *criteria* option determines when will the base class be sub-classed into this type. It is a function which takes
    the base class parse result as the paramter, and return True if the base class should be sub-classed into
    this type. *init* is the struct initializer. When create a new struct with new(), all fields will be
    initialized to 0 if *init* is not specified; if *init* is specified, the function is executed to initialize
    some fields to a pre-defined value. Usually sub-classed types need to initialize a field in the base class
    to identity the sub-class type, so it is common to use *init* together with *criteria*.
    
    The packed bytes of both "child1" and "child2" can be parsed with type "base1". The parsing is done with
    the following steps:
    - base1 is parsed, *size* is executed and extra data is stored in "_extra" attribute
    
    - every *criteria* of sub-class types is executed until one returns True
    
    - extended fields of the sub-class struct is created with "extra" data of base1, and the _extra attribute
      is removed, just like create() on a struct without base class.
      
    - if none of the *criteria* returns True, the base1 struct is unchanged.
    
    If there are a lot of sub-class types, executes a lot of *criteria* is a O(n) procedure and is not very
    efficient. The base class may set *classifier* option, which is executed and returns a hashable value.
    The sub-class type set *classifyby* option, which is a tuple of valid values. If the return value of
    *classifier* matches any value in *classifyby*, the base class is sub-classed to that type. The procedure
    is O(1).
    
    **The size of a sub-classed type is determined by the base type.** If the base type has no "extra" bytes, it
    cannot be sub-classed. If the base type does not have a *size* option, it is not possible to parse the
    struct and sub-class it from a bytes stream. But it is still possible to use create() to create the struct
    and automatically sub-class it. It is useless to set *size* option on a struct type with base type, though
    not harmful. *prepack* can still be used, and will be executed in base first, then the sub-class type.
    
    If there are still bytes not used by the sub-class type, they are stored as the "extra" data of the
    sub-class type, so the sub-class type can be sub-classed again. Also _getextra and _setextra can be used.
    
    Every time a base class is parsed, the same steps are done, so it is possible to use a base class as
    a field type, or even a array element type::
    
        base1array = nstruct((uint16, 'length'),
                            (base1[0], 'items'),
                            size = lambda x: x.length,
                            prepack = packrealsize('length'),
                            name = 'base1array')
    
    The base1array type can take any number of child1 and child2 in "items" with any order, even if they have
    different size.
    
    It is often ambiguous for a struct with additional bytes: they can be "extra" data of the struct itself,
    or they can be "extra" data of last field. Set *lastextra* option to strictly specify how they are treated.
    When *lastextra* is True, the "extra" data is considered to be "extra" data of last field if possible;
    when *lastextra* is False, the "extra" data is considered to be "extra" data of the struct itself.
    If nether is specified (or set None), the *lastextra* is determined by following rules:
    
    - A type is a variable length type if *isextra* of the type returns True. In particular, variable length
      arrays, raw bytes(*raw*, *varchr*) are variable length types.
      
    - A struct type is a variable length type if all the following criterias met:
        - it does not have a *base* type
        - it does not have a *size* option
        - *lastextra* is True (either strictly specified or automatically determined)
        
    - If the last field can be "inlined" (see option *inline*), *lastextra* is False (even if you strictly
      specify True)
      
    - The struct *lastextra* is True if the last field of the struct is a variable length type
    
    In summary, a struct *lastextra* is True if the last field is variable length, and itself is also variable
    length if no *base* or *size* is specified. For complicated struct definitions, you should consider strictly
    specify it. A struct with *lastextra* = True cannot have sub-class types since it does not have "extra" bytes.
    
    A simple enough struct may be "inlined" into another struct to improve performance, which means it
    is splitted into fields, and merged to another struct which has a field of this type. Option *inline*
    controls whether the struct should be "inlined" into other structs. By default, *inline* is automatically
    determined by the number of fields. Types with *base*, *size*, *prepack*, or *init* set will not be inlined.
    You should strictly specify *inline* = False when:
    - A inner struct has different endian with outer struct
    - The struct is a base type but *size* is not defined
    
    *formatter* and *extend* options have effect on human readable dump result. When you call dump() on
    a NamedStruct, or a value with a NamedStruct inside, and specify humanread = True, the dump result is
    converted to a human readable format. The *formatter* option is a function which takes the dump result
    of this struct (a dictionary) as a parameter. The fields in the dump result are already formatted by
    the type definitions. the *formatter* should modify the dump result and return the modified result.
    The *formatter* option is not inherited to sub-classed types, so if the struct is sub-classed, the
    *formatter* is not executed. The *formatter* option will not be executed in a embedded struct, because
    the struct shares data with the parent struct and cannot be formatted itself.
    
    *extend* is another method to modify the output format. If a type defines a "formatter"
    method, it is used by the parent struct when a struct with fields of this type is formatted. The
    "formatter" method only affects fields in structs because a primitive value (like a integer) does
    not have enough information on the original type. You may add customized formatters to a custom type::
        
        uint32_hex = prim('I', 'uint32_hex')
        uint32_hex.formatter = lambda x: ('0x%08x' % (x,))    # Convert the value to a hex string
        
    When a field of this type is defined in a struct, the dump result will be formatted with the "formatter".
    Elements of an array of this type is also formatted by the "formatter". Notice that an array type can also
    have a "formatter" defined, in that case the elements are first formatted by the inner type "formatter",
    then a list of the formatted results are passed to the array "formatter" to format the array as a whole.
    *enum* types and some pre-defined types like *ip_addr*, *mac_addr* have defined their own "formatter"s.
    
    *extend* overrides the "formatter" of specified fields. *extend* option is a dictionary, whose keys are
    field names, or tuple of names (a property path). The values are data types, instances of *nstruct*, *enum*
    or any other subclasses of *typedef*. If the new data type has a "formatter", the original formatter of
    that type is replaced by the new formatter i.e. the original formatter is NOT executed and the new formatter
    will execute with the original dump result. It is often used to override the type of a field in the base type.
    For example, a base type defineds a "flags" field but the format differs in every sub-classed type, then
    every sub-classed type may override the "flags" field to a different *enum* to show different result. If
    the extend type does not have a formatter defined, the original formatter is NOT replaced. Add a formatter
    which does not modify the result i.e. (lambda x: x) to explicitly disable the original formatter.
    
    It is also convenient to use *extend* with array fields. The "formatter" of array element are overridden to
    the new element type of the extended array type. If a "formatter" is defined on the array, it also overrides
    the original array "formatter".
    
    You may also override fields of a named field or anonymous field. Specify a key with a tuple like (f1, f2, f3...)
    will override the field self.f1.f2.f3. But notice that the original formatter is only replaced if the struct
    is "inlined" into this struct. If it is not, the formatter cannot be replaced since it is not part of the
    "formatting procedure" of this struct. For named fields, the original formatter is executed before the
    extended formatter; for anonymous fields, the original formatter is executed after the extended formatter.
    It is not assured that this order is kept unchanged in future versions. If the original type does not have
    a formatter, it is safe to extend it at any level.
    
    The *extend* options are inherited by the sub-classed types, so a sub-classed struct will still use the
    *extend* option defined in the base class. If the sub-classed type overrides a field again with *extend*
    option, the corresponding override from the base class is replaced again with the formatter from the
    sub-classed type.
    
    The overall formatting procedure of a struct is in this order:
    
    1. Dump result of every field (including fields of base type, fields of embedded structs) is calculated.
       If the field value is a struct, the struct formatting is the same as this procedure.
       
    2. Fields defined in this struct (including fields of base type, excluding fields of embedded structs)
       is formatted with the "formatter", either from the original type or from the *extend* type. If any
       descendant fields are extended with *extend*, they are also formatted.
       
    3. Embedded structs are formatted like in 2 i.e. fields with "formatter" and fields in *extend* are
       formatted.
       
    4. *formatter* is executed if it is defined in the struct type.
    
    Structs may also define "formatter" like other types, besides the *formatter* option. It is useful
    in embedded structs because the *formatter* of embedded struct is not executed. But it is only
    executed when it is contained in another struct either named or embedded, like in other types.
    
    Exceptions in formatters are always ignored. A debug level information is logged with logging module, you may
    enable debug logging to view them.
    '''
    def __init__(self, *members, **arguments):
        '''
        nstruct initializer, create a new nstruct type
        
        :param members: field definitions, either named or anonymous; named field is a tuple with 2 members
                        (type, name); anonymous field is a tuple with only 1 member (type,)
                        
        :param arguments: optional keyword arguments, see nstruct docstring for more details:
        
                size
                    A function to retrieve the struct size
                    
                prepack
                    A function to be executed just before packing, usually used to automatically store
                    the struct size to a specified field (with packsize() or packrealsize())
                    
                base
                    This type is a sub-class type of a base type, should be used with criteria and/or
                    classifyby
                    
                criteria
                    A function determines whether this struct (of base type) should be sub-classed into
                    this type
                    
                endian
                    Default to '>' as big endian or "network order". Specify '<' to use little endian.
                    
                padding
                    Default to 8. The struct is automatically padded to align to "padding" bytes boundary,
                    i.e. padding the size to be ((_realsize + (padding - 1)) // padding). Specify 1 to
                    disable alignment.
                    
                lastextra
                    Strictly specify whether the unused bytes should be considered to be the "extra" data of
                    the last field, or the "extra" data of the struct itself. See nstruct docstring for
                    more details.
                    
                name
                    Specify a readable struct name. It is always recommended to specify a name.
                    A warning is generated if you do not specify one.
                    
                inline
                    Specify if the struct can be "inlined" into another struct. See nstruct docstring for
                    details.
                    
                init
                    initializer of the struct, executed when a new struct is created with new()
                    
                classifier
                    defined in a base class to get a classify value, see nstruct docstring for details
                    
                classifyby
                    a tuple of hashable values. The values is inserted into a dictionary to quickly
                    find the correct sub-class type with classify value. See nstruct docstring for details.
                    
                formatter
                    A customized function to modify the human readable dump result. The input parameter
                    is the current dump result; the return value is the modified result, and will replace
                    the current dump result.
                    
                extend
                    Another method to modify the human readable dump result of the struct. It uses the
                    corresponding type to format the specified field, instead of the default type,
                    e.g. extend a uint16 into an enumerate type to show the enumerate name; extend
                    a 6-bytes string to mac_addr_bytes to format the raw data to MAC address format, etc.
                    
        '''
        params = ['size', 'prepack', 'base', 'criteria', 'endian', 'padding', 'lastextra', 'name', 'inline', 'init', 'classifier', 'classifyby', 'formatter', 'extend']
        for k in arguments:
            if not k in params:
                warnings.warn(StructDefWarning('Parameter %r is not recognized, is there a spelling error?' % (k,)))
        if 'name' not in arguments:
            warnings.warn(StructDefWarning('A struct is not named: %r' % (members,)))
        self.sizefunc = arguments.get('size', None)
        self.prepackfunc = arguments.get('prepack', None)
        self.base = arguments.get('base', None)
        self.criteria = arguments.get('criteria', _never)
        self.endian = arguments.get('endian', '>')
        self.padding = arguments.get('padding', 8)
        self.lastextra = arguments.get('lastextra', None)
        self.readablename = arguments.get('name', None)
        self.inlineself = arguments.get('inline', None)
        self.initfunc = arguments.get('init', None)
        self.classifier = arguments.get('classifier', None)
        self.classifyby = arguments.get('classifyby', None)
        if 'formatter' in arguments:
            self.extraformatter = arguments['formatter']
        self.formatters = {}
        self.listformatters = {}
        if self.criteria is None:
            raise ValueError('Criteria cannot be None; use default _never instead')
        if self.classifyby is not None and (isinstance(self.classifyby, str) or not hasattr(self.classifyby, '__iter__')):
            raise ValueError('classifyby must be a tuple of values')
        if self.base is not None:
            self.formatters = dict(self.base.formatters)
            self.listformatters = dict(self.base.listformatters)
            if self.inlineself:
                raise ValueError('Cannot inline a struct with a base class')
            if self.classifyby is not None and getattr(self.base, 'classifier', None) is None:
                raise ValueError('Classifier is not defined in base type %r, but sub class %r has a classify value' % (self.base, self))
            if self.classifyby is None and getattr(self.base, 'classifier', None) is not None:
                warnings.warn(StructDefWarning('Classifier is defined in base type %r, but sub class %r does not have a classifyby' % (self.base, self)))
        else:
            if self.classifyby is not None:
                raise ValueError('Classifyby is defined in %r without a base class' % (self,))
            if self.criteria is not None and self.criteria is not _never:
                raise ValueError('criteria is defined in %r without a base class' % (self,))
            if 'padding' not in arguments:
                warnings.warn(StructDefWarning('padding is not defined in %r; default to 8 (is that what you want?)' % (self,)))
        self.subclasses = []
        lastinline_format = []
        lastinline_properties = []
        seqs = []
        inline_names = {}
        endian = arguments.get('endian', '>')
        if not members:
            self.inlineself = False
        mrest = len(members)
        for m in members:
            mrest -= 1
            t = m[0]
            if isinstance(t, str):
                t = prim(t)
            elif isinstance(t, tuple):
                t = nstruct(*t, padding=1, endian=self.endian)
            if isinstance(t, arraytype):
                if hasattr(t, 'formatter'):
                    if len(m) > 1:
                        self.formatters[(m[1],)] = t.formatter
                    else:
                        self.formatters[(t,)] = t.formatter
                array = t.size
                t = t.innertype
            else:
                array = None
            if hasattr(t, 'formatter'):
                if array is None:
                    if len(m) > 1:
                        self.formatters[(m[1],)] = t.formatter
                    else:
                        self.formatters[(t,)] = t.formatter
                else:
                    if len(m) > 1:
                        self.listformatters[(m[1],)] = t.formatter
                    else:
                        self.listformatters[(t,)] = t.formatter                    
            if mrest == 0 and self.lastextra:
                inline = None
            else:
                inline = t.inline()
            if inline is not None:
                if array is not None and (array == 0 or inline[1]):
                    inline = None
            if inline is not None:
                if not inline[1]:
                    if array is None:
                        if len(m) > 1:
                            lastinline_format.append(inline[0])
                            lastinline_properties.append(((m[1],),))
                        else:
                            lastinline_format.append(str(struct.calcsize(endian + inline[0])) + 'x')
                    else:
                        if len(m) > 1:
                            lastinline_format.extend([inline[0]] * array)
                            lastinline_properties.append(((m[1],),array))
                        else:
                            lastinline_format.append(str(struct.calcsize(endian + inline[0]) * array) + 'x')
                else:
                    lastinline_format.append(inline[0])
                    for prop in inline[1]:
                        if len(m) > 1:
                            if len(prop) > 1:
                                lastinline_properties.append(((m[1],) + prop[0], prop[1]))
                            else:
                                lastinline_properties.append(((m[1],) + prop[0],))
                        else:
                            lastinline_properties.append(prop)
                    if len(m) > 1:
                        if hasattr(t, 'formatters'):
                            for k,v in t.formatters.items():
                                self.formatters[(m[1],) + k] = v
                        if hasattr(t, 'listformatters'):
                            for k,v in t.listformatters.items():
                                self.listformatters[(m[1],) + k] = v
                        if hasattr(t, 'extraformatter'):
                            self.formatters[(m[1],)] = v
                    else:
                        if hasattr(t, 'formatters'):
                            for k,v in t.formatters.items():
                                self.formatters[k] = v
                        if hasattr(t, 'listformatters'):
                            for k,v in t.listformatters.items():
                                self.listformatters[k] = v
                        if hasattr(t, 'extraformatter'):
                            self.formatters[(t,)] = v                        
            else:
                if lastinline_format:
                    seqs.append((fixedstruct(''.join(lastinline_format), lastinline_properties, padding = 1, endian = self.endian), None))
                    del lastinline_format[:]
                    lastinline_properties = []
                if len(m) > 1:
                    if array is not None:
                        seqs.append((t, (m[1], array)))
                    else:
                        seqs.append((t, (m[1],)))
                else:
                    if array is not None:
                        raise ValueError('Illegal inline array: ' + repr(m))
                    t_name = getattr(t, 'readablename', None)
                    if t_name:
                        inline_names[t_name] = len(seqs)
                    seqs.append((t, None))
        self._inline = None
        if lastinline_format:
            if not seqs:
                self.fixedstruct = fixedstruct(''.join(lastinline_format), lastinline_properties, self.sizefunc,
                                         self.prepackfunc, self.base, self.criteria, self.padding, self.endian,
                                         self.readablename, self.inlineself, self.initfunc, self, self.classifier, self.classifyby)
                self._inline = self.fixedstruct.inline()
                self.lastextra = False
            else:
                seqs.append((fixedstruct(''.join(lastinline_format), lastinline_properties, padding = 1, endian = self.endian), None))
                self.seqs = seqs
                self.lastextra = False
        else:
            if not seqs:
                self.fixedstruct = fixedstruct('', (), self.sizefunc,
                                         self.prepackfunc, self.base, self.criteria, self.padding, self.endian,
                                         self.readablename, self.inlineself, self.initfunc, self, self.classifier, self.classifyby)
                self._inline = self.fixedstruct.inline()
                self.lastextra = False
                self.propertynames = []
            else:
                self.seqs = seqs
                if self.lastextra is None:
                    lastmember = self.seqs[-1]
                    if lastmember[1] is not None and len(lastmember[1]) > 1 and lastmember[1][1] == 0:
                        self.lastextra = True
                    elif (lastmember[1] is None or len(lastmember[1]) <= 1) and lastmember[0].isextra():
                        self.lastextra = True
                    else:
                        self.lastextra = False
        self.inline_names = inline_names
        if 'extend' in arguments:
            for k,v in arguments['extend'].items():
                if isinstance(k, tuple):
                    kt = k
                else:
                    kt = (k,)
                if hasattr(v, 'formatter'):
                    self.formatters[kt] = v.formatter
                if isinstance(v, arraytype):
                    t = v.innertype
                    if hasattr(t, 'formatter'):
                        self.listformatters[kt] = t.formatter
        if self.base is not None:
            self.base.derive(self)
    def _compile(self):
        if self.base is not None:
            self.base.parser()
        if not hasattr(self, 'fixedstruct'):
            for t,name in self.seqs:
                t.parser()
        if hasattr(self, '_parser'):
            return self._parser
        if hasattr(self, 'fixedstruct'):
            p = self.fixedstruct.parser()
        else:
            p = SequencedParser([(t.parser(), name) for t,name in self.seqs], self.sizefunc, self.prepackfunc, self.lastextra,
                                None if self.base is None else self.base.parser(), self.criteria, self.padding, self.initfunc, self, self.classifier, self.classifyby)
        self._parser = p
        for sc in self.subclasses:
            sc.parser()
        return p
    def inline(self):
        return self._inline
    def __repr__(self, *args, **kwargs):
        if self.readablename is not None:
            return self.readablename
        else:
            return typedef.__repr__(self, *args, **kwargs)
    def isextra(self):
        return (not self.sizefunc) and (not self.base) and self.lastextra
    def derive(self, newchild):
        self.subclasses.append(newchild)
        if hasattr(self, '_parser'):
            newchild.parser()
    def formatdump(self, dumpvalue, v):
        return nstruct._formatdump(self, dumpvalue, v)
    @staticmethod
    def _formatdump(ns, dumpvalue, val):
        try:
            for k,v in ns.listformatters.items():
                current = dumpvalue
                try:
                    for ks in k:
                        if isinstance(ks, str):
                            current = current[ks]
                except:
                    continue
                try:
                    for i in range(0, len(current)):
                        current[i] = v(current[i])
                except:
                    NamedStruct._logger.log(logging.DEBUG, 'A formatter thrown an exception', exc_info = True)
            for k,v in ns.formatters.items():
                current = dumpvalue
                last = None
                lastkey = None
                try:
                    for ks in k:
                        if isinstance(ks, str):
                            last = current
                            lastkey = ks
                            current = current[ks]
                except:
                    continue
                if lastkey is None:
                    try:
                        dumpvalue = v(dumpvalue)
                    except: 
                        NamedStruct._logger.log(logging.DEBUG, 'A formatter thrown an exception', exc_info = True)
                else:
                    try:
                        last[lastkey] = v(current)
                    except:
                        NamedStruct._logger.log(logging.DEBUG, 'A formatter thrown an exception', exc_info = True)
            v2 = val
            while v2:
                if hasattr(v2, '_seqs'):
                    for s in v2._seqs:
                        st = s._gettype()
                        if st is not None and hasattr(st, 'formatdump'):
                            dumpvalue = st.formatdump(dumpvalue, s)
                v2 = getattr(v2, '_sub', None)
        except:
            NamedStruct._logger.log(logging.DEBUG, 'A formatter thrown an exception', exc_info = True)
        return dumpvalue
    def _reorder_properties(self, unordered_dict, ordered_dict, val):
        _basetype = val._getbasetype()
        while _basetype is not self:
            if hasattr(_basetype, '_reorder_properties'):
                _basetype._reorder_properties(unordered_dict, ordered_dict, val)
            val = val._sub
            _basetype = val._getbasetype()
        if hasattr(self, 'fixedstruct'):
            self.fixedstruct._reorder_properties(unordered_dict, ordered_dict, val)
        else:
            _seqindex = 0
            for s, name in self.seqs:
                if name is None:
                    t = val._seqs[_seqindex]._gettype()
                    if hasattr(t, '_reorder_properties'):
                        t._reorder_properties(unordered_dict, ordered_dict, val._seqs[_seqindex])
                    _seqindex += 1
                else:
                    _merge_to((name[0],), unordered_dict, ordered_dict)
    def reorderdump(self, dumpvalue, v):
        to_dict = OrderedDict()
        self._reorder_properties(dumpvalue, to_dict, v)
        _merge_dict(dumpvalue, to_dict)
        return to_dict

class enum(prim):
    '''
    Enumerate types are extensions to standard primitives. They are exactly same with the base type,
    only with the exception that when converted into human readable format with dump(), they are
    converted to corresponding enumerate names for better readability::
        
        myenum = enum('myenum', globals(), uint16,
                        MYVALUE1 = 1,
                        MYVALUE2 = 2,
                        MYVALUE3 = 3)
        
    To access the defined enumerate values::
    
        v = myenum.MYVALUE1            # 1
    
    When globals() is specified as the second parameter, the enumerate names are exported to current
    module, so it is also accessible from module globals()::
    
        v = MYVALUE2    # 2
    
    If you do not want to export the names, specify None for *namespace* parameter.
    
    A enumerate type can be bitwise, or non-bitwise. Non-bitwise enumerate types stand for values exactly
    matches the enumerate values. When formatted, they are converted to the corresponding enumerate
    name, or keep unchanged if there is not a corresponding name with that value. Bitwise enumerate
    types stand for values that are bitwise OR (|) of zero, one or more enumerate values. When a bitwise
    enumerate value is formatted, it is formatted like the following example::
        
        mybitwise = enum('mybitwise', globals(), uint16, True,
                        A = 0x1,
                        B = 0x2,
                        C = 0x4,
                        D = 0x8,
        # It is not necessary (though common) to have only 2-powered values. Merge of two or more
        # values may stand for a special meaning.
                        E = 0x9)
        
        # Formatting:
        # 0x1 -> 'A'
        # 0x3 -> 'A B'
        # 0x8 -> 'D'
        # 0x9 -> 'E'    (prefer to match more bits as a whole)
        # 0xb -> 'B E'
        # 0x1f -> 'B C E 0x10' (extra bits are appended to the sequence in hex format)
        # 0x10 -> '0x10'
        # 0x0 -> 0      (0 is unchanged)
    '''
    def __init__(self, readablename = None, namespace = None, basefmt = 'I', bitwise = False, **kwargs):
        '''
        Initializer
        :param readablename: name of this enumerate type
        
        :param namespace: A dictionary, usually specify globals(). The *kwargs* are updated to this
                        dictionary, so the enumerate names are exported to current globals and you
                        do not need to define them in the module again. None to disable this feature.
                        
        :param basefmt: base type of this enumerate type, can be format strings or a *prim* type
        
        :param bitwise: if True, the enumerate type is bitwise, and will be formatted to space-separated
                        names; if False, the enumerate type is non-bitwise and will be formatted to a
                        single name.
                        
        :param kwargs: ENUMERATE_NAME = ENUMERATE_VALUE format definitions of enumerate values.
        '''
        if hasattr(basefmt, '_format'):
            prim.__init__(self, basefmt._format, readablename, basefmt._endian, basefmt._strict)
        else:
            prim.__init__(self, basefmt, readablename)
        self._values = dict(kwargs)
        self._bitwise = bitwise
        for k,v in kwargs.items():
            setattr(self, k, v)
        if namespace is not None:
            for k,v in kwargs.items():
                namespace[k] = v
    def getName(self, value, defaultName = None):
        '''
        Get the enumerate name of a specified value.
        :param value: the enumerate value
        :param defaultName: returns if the enumerate value is not defined
        :returns: the corresponding enumerate value or *defaultName* if not found
        '''
        for k,v in self._values.items():
            if v == value:
                return k
        return defaultName
    def getValue(self, name, defaultValue = None):
        '''
        Get the enumerate value of a specified name.
        :param name: the enumerate name
        :param defaultValue: returns if the enumerate name is not defined
        :returns: the corresponding enumerate value or *defaultValue* if not found
        '''
        return self._values.get(name, defaultValue)
    def importAll(self, gs):
        '''
        Import all the enumerate values from this enumerate to *gs*
        :param gs: usually globals(), a dictionary. At lease __setitem__ should be implemented if not a dictionary.
        '''
        for k,v in self._values.items():
            gs[k] = v
    def extend(self, namespace = None, name = None, **kwargs):
        '''
        Create a new enumerate with current values merged with new enumerate values
        :param namespace: same as __init__
        :param name: same as __init__
        :param kwargs: same as __init__
        :returns: a new enumerate type
        '''
        if name is None:
            name = self._readablename
        d = dict(self._values)
        d.update(kwargs)
        return enum(name, namespace, self, self._bitwise, **d)
    def tostr(self, value):
        '''
        Convert the value to string representation. The formatter is first used,
        and if the return value of the formatter is still a integer, it is converted
        to string. Suitable for human read represent.
        :param value: enumerate value
        :returns: a string represent the enumerate value
        '''
        return str(self.formatter(value))
    def getDict(self):
        '''
        Returns a dictionary whose keys are enumerate names, and values are corresponding
        enumerate values.
        '''
        return self._values
    def __contains__(self, item):
        '''
        Test whether a value is defined.
        '''
        return item in self._values.values()
    def astype(self, primtype, bitwise = False):
        '''
        Create a new enumerate type with same enumerate values but a different primitive type
        e.g. convert a 16-bit enumerate type to fit in a 32-bit field.
        :param primtype: new primitive type
        :param bitwise: whether or not the new enumerate type should be bitwise
        '''
        return enumref(self, primtype, bitwise)
    def formatter(self, value):
        '''
        Format a enumerate value to enumerate names if possible. Used to generate human readable
        dump result.
        '''
        if not self._bitwise:
            n = self.getName(value)
            if n is None:
                return value
            else:
                return n
        else:
            names = []
            for k,v in sorted(self._values.items(), key=lambda x: x[1], reverse=True):
                if (v & value) == v:
                    names.append(k)
                    value = value ^ v
            names.reverse()
            if value != 0:
                names.append(hex(value))
            if not names:
                return 0 
            return ' '.join(names)
    def merge(self, otherenum):
        '''
        Return a new enumerate type, which has the same primitive type as this type,
        and has enumerate values defined both from this type and from *otherenum*
        :param otherenum: another enumerate type
        :returns: a new enumerate type
        '''
        return self.extend(None, **otherenum.getDict())

class enumref(prim):
    '''
    A enum type references another enum type
    '''
    def __init__(self, refenum, basefmt = 'I', bitwise = False):
        if hasattr(basefmt, '_format'):
            prim.__init__(self, basefmt._format, refenum._readablename, basefmt._endian, basefmt._strict)
        else:
            prim.__init__(self, basefmt, refenum._readablename)
        self._ref = refenum
        self._bitwise = bitwise
    def getName(self, value, defaultName = None):
        for k,v in self._ref._values.items():
            if v == value:
                return k
        return defaultName
    def getValue(self, name, defaultValue = None):
        return self._ref._values.get(name, defaultValue)
    def importAll(self, gs):
        for k,v in self._ref._values.items():
            gs[k] = v
    def extend(self, namespace = None, name = None, **kwargs):
        if name is None:
            name = self._readablename
        d = dict(self._ref._values)
        d.update(kwargs)
        return enum(name, namespace, self, **d)
    def tostr(self, value):
        return str(self.formatter(value))
    def getDict(self):
        return self._ref._values
    def __contains__(self, item):
        return item in self._ref._values.values()
    def astype(self, primtype, bitwise = False):
        return enumref(self._ref, primtype, bitwise)
    def formatter(self, value):
        if not self._bitwise:
            n = self.getName(value)
            if n is None:
                return value
            else:
                return n
        else:
            names = []
            for k,v in sorted(self._ref._values.items(), key=lambda x: x[1], reverse=True):
                if (v & value) == v:
                    names.append(k)
                    value = value ^ v
            names.reverse()
            if value != 0:
                names.append(hex(value))
            if not names:
                return 0 
            return ' '.join(names)
    def merge(self, otherenum):
        return self.extend(None, **otherenum.getDict())

class OptionalParser(Parser):
    '''
    Parser for *optional* type
    '''
    def __init__(self, basetypeparser, name, criteria, typedef, prepackfunc = None):
        Parser.__init__(self, padding = 1, typedef=typedef, prepackfunc=prepackfunc)
        self.basetypeparser = basetypeparser
        self.name = name
        self.criteria = criteria
    def _parseinner(self, data, s, create = False):
        if self.criteria(s):
            if create:
                inner = self.basetypeparser.create(data, None)
                size = len(data)
            else:
                r = self.basetypeparser.parse(data, None)
                if r is None:
                    return None
                (inner, size) = r
            setattr(s._target, self.name, inner)
            return size
        else:
            return 0       
    def _parse(self, data, inlineparent = None):
        s = _create_struct(self, inlineparent)
        size = self._parseinner(data, s)
        if size is None:
            return None
        else:
            return (s, size)
    def _new(self, inlineparent=None):
        return _create_struct(self, inlineparent)
    def unpack(self, data, namedstruct):
        size = self._parseinner(data, namedstruct, True)
        if size is None:
            raise BadLenError('Bad Len')
        else:
            return data[size:]
    def pack(self, namedstruct):
        data = b''
        if hasattr(namedstruct, self.name):
            data = self.basetypeparser.tobytes(getattr(namedstruct, self.name))
        return data
    def sizeof(self, namedstruct):
        if hasattr(namedstruct, self.name):
            return self.basetypeparser.paddingsize(getattr(namedstruct, self.name))
        else:
            return 0

class optional(typedef):
    '''
    Create a "optional" field in a struct. On unpacking, the field is only parsed when the specified
    criteria is met; on packing, the field is only packed when it appears (hasattr returns True).
    This function may also be done with sub-classing, but using *optional* is more convenient::
    
        myopt = nstruct((uint16, 'data'),
                        (uint8, 'hasextra'),
                        (optional(uint32, 'extra', lambda x: x.hasextra),),
                        name = 'myopt',
                        prepack = packexpr(lambda x: hasattr(x, 'extra'), 'hasextra'))
    
    - A optional type is placed in an anonymous field. In fact it creates an embedded struct with only
      one (optional) field.
      
    - The criteria can only use fields that are defined before the optional field because the other fields
      are not yet parsed.
      
    - Usually you should specify a *prepack* function to pack some identifier into the struct to identify
      that the optional field appears.
      
    - The optional field does not exists when the struct is created with new(). Simply set a value to the
      attribute to create the optional field: myopt(data = 7, extra = 12)
      
    - The optional type is a variable length type if and only if the *basetype* is a variable length type
    '''
    def __init__(self, basetype, name, criteria, prepackfunc = None):
        '''
        Initializer.
        
        :param basetype: the optional field type
        
        :param name: the name of the optional field
        
        :param criteria: a function to determine whether the optional field should be parsed.
        
        :param prepackfunc: function to execute before pack, like in nstruct
        '''
        self.basetype = basetype
        self.criteria = criteria
        self.prepackfunc = prepackfunc
        if name is None:
            raise ParseError('Optional member cannot be in-line member')
        self.name = name
        self._formatter = None
        self._listformatter = None
        if isinstance(basetype, arraytype):
            t = basetype.innertype
            if hasattr(t, 'formatter'):
                self._listformatter = t.formatter
        if hasattr(basetype, 'formatter'):
            self._formatter = basetype.formatter
        
    def array(self, size):
        raise TypeError('optional type cannot form array')
    def _compile(self):
        return OptionalParser(self.basetype.parser(), self.name, self.criteria, self, self.prepackfunc)
    def isextra(self):
        return self.basetype.isextra()
    def __repr__(self, *args, **kwargs):
        return repr(self.basetype) + '?'
    def formatdump(self, dumpvalue, val):
        try:
            if self.name in dumpvalue:
                v = dumpvalue[self.name]
                if self._listformatter:                    
                    for i in range(0, len(v)):
                        try:
                            v[i] = self._listformatter(v[i])
                        except:
                            NamedStruct._logger.log(logging.DEBUG, 'A formatter thrown an exception', exc_info = True)
                if self._formatter:
                    dumpvalue[self.name] = self._formatter(v)                            
            v2 = val
            while v2:
                if hasattr(v2, '_seqs'):
                    for s in v2._seqs:
                        st = s._gettype()
                        if st is not None and hasattr(st, 'formatdump'):
                            dumpvalue = st.formatdump(dumpvalue, s)
                v2 = getattr(v2, '_sub', None)
        except:
            NamedStruct._logger.log(logging.DEBUG, 'A formatter thrown an exception', exc_info = True)            
        return dumpvalue
    def _reorder_properties(self, unordered_dict, ordered_dict, val):
        _merge_to((self.name,), unordered_dict, ordered_dict)

class DArrayParser(Parser):
    '''
    Parser for *darray*
    '''
    def __init__(self, innertypeparser, name, size, typedef, padding = 1, prepackfunc = None):
        Parser.__init__(self, padding = padding, typedef=typedef, prepackfunc=prepackfunc)
        self.innertypeparser = innertypeparser
        self.name = name
        self.size = size
    def _parseinner(self, data, s, create = False):
        l = self.size(s)
        result = []
        start = 0
        for _ in range(0, l):
            r = self.innertypeparser.parse(data[start:], None)
            if r is None:
                return None
            (inner, size) = r
            result.append(inner)
            start += size
        setattr(s._target, self.name, result)
        return start
    def _parse(self, data, inlineparent = None):
        s = _create_struct(self, inlineparent)
        size = self._parseinner(data, s)
        if size is None:
            return None
        else:
            return (s, size)
    def _new(self, inlineparent=None):
        s = _create_struct(self, inlineparent)
        setattr(s._target, self.name, [])
        return s
    def unpack(self, data, namedstruct):
        size = self._parseinner(data, namedstruct, True)
        if size is None:
            raise BadLenError('Bad Len')
        else:
            return data[size:]
    def pack(self, namedstruct):
        return b''.join(self.innertypeparser.tobytes(i) for i in getattr(namedstruct, self.name))
    def sizeof(self, namedstruct):
        return sum(self.innertypeparser.paddingsize(i) for i in getattr(namedstruct, self.name))

class darray(typedef):
    '''
    Create a dynamic array field in a struct. The length of the array is calculated by other fields of
    the struct. If the total size of the struct is stored, you should consider use *size* option and a
    variable length array (sometype[0]) as the last field, instead of calculating the array size yourself.
    If the array contains very simple elements like primitives, it may be a better idea to calculate the
    total size of the struct from the array length and return the size from *size* option, because if the
    data is incomplete, the parsing quickly stops without the need to parse part of the array.
    Only use dynamic array when: the bytes size of the array cannot be determined, but the element size
    of the array is stored::
    
        myopt = nstruct((uint16, 'data'),
                        (uint8, 'extrasize'),
                        (darray(mystruct, 'extras', lambda x: x.extrasize),),
                        name = 'myopt',
                        prepack = packexpr(lambda x: len(x.extras), 'hasextra'))
    
    - A darray type is placed in an anonymous field. In fact it creates an embedded struct with only
      one field.
      
    - The *size* function can only use fields that are defined before the optional field because the other
      fields are not yet parsed.
      
    - Usually you should specify a *prepack* function to pack the array size into the struct
    
    - *padding* option is available if it is necessary to pad the bytes size of the whole array to multiply
      of *padding*
      
    - You can use *extend* with an array type (mystruct2[0]) to override the formatting of inner types or the
      whole array
    '''
    def __init__(self, innertype, name, size, padding = 1, prepack = None):
        '''
        Initializer.
        
        :param innertype: type of array element
        
        :param name: field name
        
        :param size: a function to calculate the array length
        
        :param padding: align the array to padding-bytes boundary, like in nstruct
        
        :param prepack: prepack function, like in nstruct
        '''
        self.innertype = innertype
        self.size = size
        if name is None:
            raise ParseError('Dynamic array member cannot be in-line member')
        self.name = name
        self.padding = padding
        self.prepackfunc = prepack
    def array(self, size):
        raise TypeError('Dynamic array type cannot form array')
    def _compile(self):
        return DArrayParser(self.innertype.parser(), self.name, self.size, self, self.padding, self.prepackfunc)
    def isextra(self):
        return False
    def __repr__(self, *args, **kwargs):
        return repr(self.innertype) + '[]'
    def formatdump(self, dumpvalue, val):
        try:
            if hasattr(self.innertype, 'formatter'):
                listformatter = self.innertype.formatter
                v = dumpvalue[self.name]
                for i in range(0, len(v)):
                    try:
                        v[i] = listformatter(v[i])
                    except:
                        NamedStruct._logger.log(logging.DEBUG, 'A formatter thrown an exception', exc_info = True)            
            v2 = val
            while v2:
                if hasattr(v2, '_seqs'):
                    for s in v2._seqs:
                        st = s._gettype()
                        if st is not None and hasattr(st, 'formatdump'):
                            dumpvalue = st.formatdump(dumpvalue, s)
                v2 = getattr(v2, '_sub', None)
        except:
            NamedStruct._logger.log(logging.DEBUG, 'A formatter thrown an exception', exc_info = True)            
        return dumpvalue


class BitfieldParser(Parser):
    '''
    Parser for *bitfield*
    '''
    def __init__(self, basetypeparser, fields, init, typedef, prepackfunc = None):
        Parser.__init__(self, padding = 1, initfunc = init, typedef=typedef, prepackfunc=prepackfunc)
        self.basetypeparser = basetypeparser
        self.fields = fields
    def _parseinner(self, data, s, create = False):
        if create:
            inner = self.basetypeparser.create(data, None)
            size = len(data)
        else:
            r = self.basetypeparser.parse(data, None)
            if r is None:
                return None
            (inner, size) = r
        totalbits = size * 8
        for f,n in self.fields:
            if len(f) > 2:
                width = f[2]
                mask = (1<<width) - 1
                setattr(s._target, n, [((inner >> (totalbits - b - width)) & mask) for b in range(f[0], f[1], width)])
            else:
                mask = (1<<(f[1] - f[0])) - 1
                setattr(s._target, n, (inner >> (totalbits - f[1])) & mask)
        return size
    def _parse(self, data, inlineparent = None):
        s = _create_struct(self, inlineparent)
        size = self._parseinner(data, s)
        if size is None:
            return None
        else:
            return (s, size)
    def _new(self, inlineparent=None):
        s = _create_struct(self, inlineparent)
        s._unpack(self.basetypeparser.tobytes(self.basetypeparser.new()))
        return s
    def unpack(self, data, namedstruct):
        size = self._parseinner(data, namedstruct, True)
        if size is None:
            raise BadLenError('Bad Len')
        else:
            return data[size:]
    def pack(self, namedstruct):
        data = 0
        totalbits = self.basetypeparser.sizeof(0) * 8
        for f,n in self.fields:
            if len(f) > 2:
                width = f[2]
                mask = (1<<width) - 1
                for v,b in zip(getattr(namedstruct, n), range(f[0], f[1], width)):
                    data |= ((v & mask) << (totalbits - b - width))
            else:
                mask = (1<<(f[1] - f[0])) - 1
                data |= ((getattr(namedstruct, n) & mask) << (totalbits - f[1]))
        return self.basetypeparser.tobytes(data)
    def sizeof(self, namedstruct):
        return self.basetypeparser.sizeof(0)

class bitfield(typedef):
    '''
    *bitfield* are mini-struct with bit fields. It splits a integer primitive type like uint32
    to several bit fields. The splitting is always performed with big-endian, which means the
    fields are ordered from the highest bits to lowest bits. Base type endian only affects the
    bit order when parsing the bytes to integer, but not the fields order. Unlike bit-fields in
    C/C++, the fields does not need to be aligned to byte boundary, and no padding between the
    fields unless defined explicitly. For example::
    
        mybit = bitfield(uint64,
                        (4, 'first'),
                        (5, 'second'),
                        (2,),    # Padding bits
                        (19, 'third'),    # Can cross byte border
                        (1, 'array', 20), # A array of 20 1-bit numbers
                        name = 'mybit',
                        init = packvalue(2, 'second'),
                        extend = {'first': myenum, 'array': myenum2[20]})
    '''
    def __init__(self, basetype, *properties, **arguments):
        '''
        Initializer
        :param basetype: A integer primitive type to provide the bits
        
        :param properties: placed arguments, definitions of fields. Each argument is a tuple,
                           the first element is the bit-width, the second element is a field name.
                           If a third element appears, the field is an bit-field array; if the
                           second element does not appear, the field is some padding bits.
                           
        :param arguments: keyword options
        
                        name
                            the type name
                            
                        init
                            a initializer to initialize the struct
                            
                        extend
                            similar to *extend* option in nstruct
                            
                        formatter
                            similar to *formatter* option in nstruct
                        
                        prepack
                            similar to *prepack* option in nstruct
        '''
        params = ['name', 'init', 'extend', 'formatter', 'prepack']
        for k in arguments:
            if not k in params:
                warnings.warn(StructDefWarning('Parameter %r is not recognized, is there a spelling error?' % (k,)))
        self.basetype = basetype
        self.properties = properties
        self.readablename = arguments.get('name')
        self.initfunc = arguments.get('init')
        self.prepackfunc = arguments.get('prepack')
        fields = []
        start = 0
        for p in properties:
            if len(p) > 3 or len(p) < 1:
                raise ValueError('Unknown bit-field definition')
            elif len(p) == 3:
                # Bit-field array
                fields.append(((start, start + p[0] * p[2], p[0]), p[1]))
                start += p[0] * p[2]
            elif len(p) == 2:
                fields.append(((start, start + p[0]), p[1]))
                start += p[0]
            else:
                start += p[0]
        self.fields = fields
        minsize = (start + 7) // 8
        bs = basetype.parser().sizeof(0)
        if minsize > bs:
            raise ValueError('Bit-fields need %d bytes, underline type has only %d bytes' % (minsize, bs))
        self.formatters = {}
        self.listformatters = {}
        if 'extend' in arguments:
            for k,v in arguments['extend'].items():
                if isinstance(k, tuple):
                    if len(k) == 1:
                        k = k[0]
                    else:
                        raise ValueError('Cannot extend bitfield with property path')
                kt = k
                if hasattr(v, 'formatter'):
                    self.formatters[kt] = v.formatter
                if isinstance(v, arraytype):
                    t = v.innertype
                    if hasattr(t, 'formatter'):
                        self.listformatters[kt] = t.formatter
        if 'formatter' in arguments:
            self.extraformatter = arguments['formatter']
    def _compile(self):
        return BitfieldParser(self.basetype.parser(), self.fields, self.initfunc, self, self.prepackfunc)
    def isextra(self):
        return self.basetype.isextra()
    def __repr__(self, *args, **kwargs):
        if self.readablename is not None:
            return self.readablename
        else:
            return typedef.__repr__(self, *args, **kwargs)
    def formatdump(self, dumpvalue, val):
        try:
            for k,v in self.listformatters.items():
                try:
                    current = dumpvalue[k]
                except:
                    continue
                try:
                    for i in range(0, len(current)):
                        try:
                            current[i] = v(current[i])
                        except:
                            NamedStruct._logger.log(logging.DEBUG, 'A formatter thrown an exception', exc_info = True)                            
                except:
                    NamedStruct._logger.log(logging.DEBUG, 'A formatter thrown an exception', exc_info = True)
            for k,v in self.formatters.items():
                try:
                    dumpvalue[k] = v(dumpvalue[k])
                except:
                    NamedStruct._logger.log(logging.DEBUG, 'A formatter thrown an exception', exc_info = True)
            v2 = val
            while v2:
                if hasattr(v2, '_seqs'):
                    for s in v2._seqs:
                        st = s._gettype()
                        if st is not None and hasattr(st, 'formatdump'):
                            dumpvalue = st.formatdump(dumpvalue, s)
                v2 = getattr(v2, '_sub', None)
        except:
            NamedStruct._logger.log(logging.DEBUG, 'A formatter thrown an exception', exc_info = True)
        return dumpvalue
    def _reorder_properties(self, unordered_dict, ordered_dict, val):
        for _, name in self.fields:
            _merge_to((name,), unordered_dict, ordered_dict)
    def reorderdump(self, dumpvalue, v):
        to_dict = OrderedDict()
        self._reorder_properties(dumpvalue, to_dict, v)
        _merge_dict(dumpvalue, to_dict)
        return to_dict


class VariantParser(Parser):
    '''
    Parser for *variant* type
    '''
    def __init__(self, typedef, header = None, classifier = None, prepackfunc = None, padding = 1):
        Parser.__init__(self, padding = padding, typedef=typedef, classifier=classifier, prepackfunc=prepackfunc)
        self.header = header
    def _parseinner(self, data, s, create = False):
        s._seqs = []
        if self.header is not None:
            # Create an embedded struct
            r = self.header.parse(data, s._target)
            if r is None:
                return None
            else:
                h, start = r
                s._seqs.append(h)
        else:
            start = 0
        subp = None
        clsfr = self.classifier
        if clsfr is not None:
            clsvalue = clsfr(s)
            subp = self.subindices.get(clsvalue)
        if subp is None:
            for sc in self.subclasses:
                if sc.isinstance(s):
                    subp = sc
                    break
        if subp is None:
            return start
        else:
            if create:
                inner = subp._create(data[start:], s._target)
                size = len(data)
            else:
                r = subp._parse(data[start:], s._target)
                if r is None:
                    return None
                (inner, size) = r
            s._extend(inner)
            return start + size
    def _parse(self, data, inlineparent = None):
        s = _create_struct(self, inlineparent)
        size = self._parseinner(data, s)
        if size is None:
            return None
        else:
            return (s, size)
    def _new(self, inlineparent=None):
        s = _create_struct(self, inlineparent)
        inlineparent = s._target
        s._seqs = []
        if self.header is not None:
            s._seqs.append(self.header.new(inlineparent))
        return s
    def unpack(self, data, namedstruct):
        size = self._parseinner(data, namedstruct, True)
        if size is None:
            raise BadLenError('Bad Len')
        else:
            return data[size:]
    def pack(self, namedstruct):
        if self.header is not None:
            return self.header.tobytes(namedstruct._seqs[0])
        else:
            return b''
    def sizeof(self, namedstruct):
        if self.header is not None:
            return self.header.paddingsize(namedstruct._seqs[0])
        else:
            return 0


class nvariant(typedef):
    '''
    An *nvariant* struct is a specialized base for *nstruct*. Different from normal *nstruct*, it does not
    have *size* option, instead, its size is determined by subclassed structs.
    
    A *variant* type can not be parsed with enough compatibility: if a new type of subclassed struct is
    not recognized, the whole data may be corrupted. It is not recommended to use this type for newly
    designed data structures, only use them to define data structures that: already exists; cannot be
    parsed by other ways. 
    '''
    def __init__(self, name, header = None, classifier = None, prepackfunc = None, padding = 1):
        '''
        Initializer.
        
        :param name: type name

        :param header: An embedded type, usually an nstruct. It is embedded to the nvariant and parsed before
               subclassing.
                
        :param classifier: same as *nstruct*
        
        :param prepackfunc: same as *nstruct*
        '''
        self.subclasses = []
        self.classifier = classifier
        self.prepackfunc = prepackfunc
        self.padding = padding
        self.header = header
        self.inline_names = {}
        self.formatters = {}
        self.listformatters = {}
        if header is not None:
            header_name = getattr(header, 'readablename', None)
            if header_name is not None:
                self.inline_names[header_name] = 0
            if hasattr(header, 'formatters'):
                for k,v in header.formatters.items():
                    self.formatters[k] = v
            if hasattr(header, 'listformatters'):
                for k,v in header.listformatters.items():
                    self.listformatters[k] = v
            if hasattr(header, 'extraformatter'):
                self.formatters[(header,)] = v                        
        if name is None:
            warnings.warn(StructDefWarning('nvariant type is not named'))
        self.readablename = name
    def _compile(self):
        if self.header is not None:
            hp = self.header.parser()
        else:
            hp = None
        self._parser = VariantParser(self, hp, self.classifier, self.prepackfunc, self.padding)
        for sc in self.subclasses:
            sc.parser()
        return self._parser
    def isextra(self):
        return False
    def __repr__(self, *args, **kwargs):
        if self.readablename is not None:
            return self.readablename
        else:
            return '<variant>'
    def formatdump(self, dumpvalue, val):
        return nstruct._formatdump(self, dumpvalue, val)
    def derive(self, newchild):
        self.subclasses.append(newchild)
        if hasattr(self, '_parser'):
            newchild.parser()
    def _reorder_properties(self, unordered_dict, ordered_dict, val):
        t = val._seqs[0]._gettype()
        if t is not None and hasattr(t, '_reorder_properties'):
            t._reorder_properties(unordered_dict, ordered_dict, val._seqs[0])
    def reorderdump(self, dumpvalue, v):
        to_dict = OrderedDict()
        self._reorder_properties(dumpvalue, to_dict, v)
        _merge_dict(dumpvalue, to_dict)
        return to_dict
