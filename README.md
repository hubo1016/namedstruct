# namedstruct

[![Build Status](https://travis-ci.org/hubo1016/namedstruct.svg?branch=master)](https://travis-ci.org/hubo1016/namedstruct)
[![PyPI](https://img.shields.io/pypi/v/nstruct.svg)](https://pypi.python.org/pypi/nstruct)

Define complicated C/C++ structs in Python with variable length arrays, header/extend relations, extensible structures in one time, parse/rebuild them with a single line of code

This library is designed for Openflow structures parsing in [VLCP](https://github.com/hubo1016/vlcp) project.
It is also used to parse GZIP header, HTTP2 frames, etc.

Some documents are hosted on [readthedocs](http://namedstruct.readthedocs.org/en/latest/) or [pythonhosted.org](https://pythonhosted.org/nstruct/). For a quick guide see
[Basic Tutorial](http://namedstruct.readthedocs.org/en/latest/tutorial.html#basic-tutorial).

Some examples are given in *misc* package, including a complete definition of Openflow 1.0, 1.3 and Nicira
extensions. They are not part of the library but can be used freely. The Openflow structures are very
complicated C/C++ structures, usually you will need more than 6000 lines of **hard-coded, not extensible,
uneasy to maintain** Python code to parse them. With *namedstruct*, I just modified the openflow.h, nicira_ext.h
headers with some rules and created the types in **several days**. I even keep the license and remarks unchanged.

Another example parses GZIP file header, which is a little-endian format. It is used in HTTP implementation in VLCP
to extract the deflate data from a GZIP-encoded content without creating a in-memory file. 

The project name in PyPI is nstruct. Install with PyPI::

    pip install nstruct

This project supports both Python2.x and Python3.x.

Some quick examples:

```Python
###### BASIC STRUCT #####

from namedstruct import *
mytype = nstruct((uint16, 'myshort'),  # unsigned short int
                (uint8, 'mybyte'),       # unsigned char
                (uint8,),               # a padding byte of unsigned char
                (char[5], 'mystr'),   # a 16-byte bytes string
                (uint8,),
                (uint16[5], 'myarray'),    # 
                name = 'mytype',
                padding = 1)
# Create an object
obj0 = mytype()
# Access a field
s = obj0.myshort
obj0.myshort = 12
# Create an object with the specified fields initialized
obj1 = mytype(myshort = 2, mystr = b'123', myarray = [1,2,3,4,5]) 
# Unpack an object from stream, return the object and bytes size used
obj2,size = mytype.parse(b'\x00\x02\x01\x00123\x00\x00\x00\x00\x01\x00\x02\x00\x03\x00\x04\x00\x05')
# Unpack an object from packed bytes
obj3 = mytype.create(b'\x00\x02\x01\x00123\x00\x00\x00\x00\x01\x00\x02\x00\x03\x00\x04\x00\x05')
# Estimate the struct size
size = len(obj0)
# Estimate the struct size excludes automatic padding bytes
size2 = obj0._realsize()
# Pack the object
b = obj0._tobytes()
b2 = mytype.tobytes(obj0)

# Use the type in other structs

mytype2 = nstruct((mytype, 'mydata'),
                (mytype[4], 'mystructarray'),
                name = 'mytype2',
                padding = 1)

obj4 = mytype2()
obj4.mydata.myshort = 12
obj4.mystructarray[0].mybyte = 7
b3 = obj4._tobytes()

###### VARIABLE LENGTH TYPES #####

my_unsize_struct = nstruct((uint16, 'length'),
                        (raw, 'data'),
                        padding = 1,
                        name = 'my_unsize_struct')

"""
>>> my_unsize_struct.create(b'\x00\x07abcde').data
b'abcde'
>>> my_unsize_struct.parse(b'\x00\x07abcde')[0].data
b''
"""

my_size_struct = nstruct((uint16, 'length'),
                        (raw, 'data'),
                        padding = 1,
                        name = 'my_size_struct',
                        prepack = packrealsize('length'),
                        size = lambda x: x.length)
"""
packrealsize('length') is equivalent to:
    
    def _packsize(x):
        x.length = x._realsize()
"""

"""
>>> my_unsize_struct(data = b'abcde')._tobytes()
b'\x00\x07abcde'
>>> my_unsize_struct.parse(b'\x00\x07abcde')[0].data
b'abcde'
"""

##### EXTENDING #####

my_base = nstruct((uint16, 'length'),
                 (uint8, 'type'),
                 (uint8, 'basedata'),
                 name = 'my_base',
                 size = lambda x: x.length,
                 prepack = packrealsize('length'),
                 padding = 4)

my_child1 = nstruct((uint16, 'data1'),
                    (uint8, 'data2'),
                    name = 'my_child1',
                    base = my_base,
                    criteria = lambda x: x.type == 1,
                    init = packvalue(1, 'type'))

my_child2 = nstruct((uint32, 'data3'),
                   name = 'my_child2',
                   base = my_base,
                   criteria = lambda x: x.type == 2,
                   init = packvalue(2, 'type'))

"""
Fields and most base class options are inherited, e.g. size, prepack, padding
>>> my_child1(basedata = 1, data1 = 2, data2 = 3)._tobytes()
b'\x00\x07\x01\x01\x00\x02\x03\x00'
>>> my_child2(basedata = 1, data3 = 4)._tobytes()
b'\x00\x08\x02\x01\x00\x00\x00\x04'
"""

# Fields in child classes are automatically parsed when the type is determined
obj1, _ = my_base.parse(b'\x00\x07\x01\x01\x00\x02\x03\x00')
"""
>>> obj1.basedata
1
>>> obj1.data1
2
>>> obj1.data2
3
>>> obj1._gettype()
my_child1
"""

# Base type can be used in fields or arrays of other structs

my_base_array = nstruct((uint16, 'total_len'),
                       (my_base[0], 'array'),
                       name = 'my_base_array',
                       padding = 1,
                       size = lambda x: x.total_len,
                       prepack = packrealsize('total_len'))

obj2 = my_base_array()
obj2.array.append(my_child1(data1 = 1, data2 = 2, basedata = 3))
obj2.array.append(my_child2(data3 = 4, basedata = 5))
"""
>>> obj2._tobytes()
b'\x00\x12\x00\x07\x01\x03\x00\x01\x02\x00\x00\x08\x02\x05\x00\x00\x00\x04'
"""
obj3, _ = my_base_array.parse(b'\x00\x12\x00\x07\x01\x03\x00\x01\x02\x00\x00\x08\x02\x05\x00\x00\x00\x04')
"""
>>> obj3.array[0].data2
2
"""

```
