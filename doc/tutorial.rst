.. _tutorial:
.. highlight:: python

Basic Tutorial
==============

The common usage of namedstruct is to create **type definitions** with interfaces like
:py:class:`namedstruct.nstruct` and :py:class:`namedstruct.enum`,
use :py:func:`namedstruct.typedef.parse` or :py:func:`namedstruct.typedef.create` interfaces
on the created types to parse a packed struct bytes to a Python object, use
:py:func:`namedstruct.typedef.new` (or directly :py:func:`namedstruct.typedef.__call__` of the
created type, like normal Python classes) to create new objects of the defined type, and use
:py:func:`namedstruct.NamedStruct._tobytes` to convert objects to packed bytes.
Use :py:func:`namedstruct.dump` to convert the Python object to json-serializable format.

.. _basicusage:

-----------
Basic Usage
-----------

Create structs with pre-defined primitive types or other defined types::
    
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

The struct is equivalent to C struct definition:

.. code-block:: c
	
    typedef struct mytype{
        unsigned short int myshort;
        unsigned char mybyte;
        char _padding;
        unsigned char mystr[5];
        char _padding2;
        unsigned short myarray[5];
    }mytype;
	

.. _variablelengthstruct:

--------------------------
Variable Length Data Types
--------------------------

Some data types can have variable length. they can consume extra data::

    myvartype = nstruct((uint16, 'a'),
                        (uint16[0], 'extra'),
                        padding = 1,
                        name = 'myvartype')
    
    """
    >>> myvartype.create(b'\x00\x02').extra
    []
    >>> myvartype.create(b'\x00\x02\x00\x01\x00\x003\x00\x05').extra
    [1,3,5]
    """
    
    obj1 = myvartype()
    obj1.extra.append(5)
    obj1.extra.extend((1,2,3))
    """
    >>> obj1._tobytes()
    b'\x00\x00\x05\x00\x01\x00\x02\x00\x03'
    """
    
    myvartype2 = nstruct((uint16, 'a'),
                        (raw, 'data'),
                        padding = 1,
                        name = 'myvartype2')
    
    """
    >>> myvartype.create(b'\x00\x01abcde').data
    b'abcde'
    >>> myvartype(a = 1, data = b'XYZ')._tobytes()
    b'\x00\x01XYZ'
    """
    
Variable length data types do not have determined length, so they cannot be parsed correctly themselves.
The outer-struct should store some extra informations to determine the correct length. Specify a *size*
option to calculate the correct struct size. Most times the total size of the struct is stored in a field,
return that value to let the struct parses correctly::

    from namedstruct import nstruct, uint16, raw, packrealsize
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

.. _commonoptions:

--------------
Common Options
--------------

*name* defines the struct name. It is used in many ways, so it is recommended to define a name option
for any struct::
    
    struct1 = nstruct((uint8,'data'),name = 'struct1')
    """
    >>> repr(struct1)
    'struct1'
    """

*init* defines the struct initializer. It is a function executed every time a new instance of this type
is created with *new* (*packvalue* is a helper function which returns a function setting specified value
to corresponding attribute when executing)::

    from namedstruct import nstruct, uint8, packvalue
    struct2 = nstruct((uint8,'data'),name = 'struct2',init = packvalue(1, 'data'))

    """
    >>> struct2().data
    1
    """
     
*prepack* is a function executed just before struct pack. It is useful to automatically generate fields related
to other fields, like checksum or struct size (*packexpr* is a helper function which evaluates the function
with the struct as the first argument and stores the return value to the specified attribute)::

    from namedstruct import nstruct, uint8, packexpr
    struct3 = nstruct((uint8, 'a'),
                    (uint8, 'b'),
                    (uint8, 'sum'),
                    name = 'struct3',
                    prepack = packexpr(lambda x: x.a + x.b, 'sum')
                    )
    """
    Equivalent to:
    
        def _prepack_func(x):
            x.sum = x.a + x.b
        struct3 = nstruct((uint8, 'a'),
                        (uint8, 'b'),
                        (uint8, 'sum'),
                        name = 'struct3',
                        prepack = _prepack_func
                        )
    """

The fields are in big-endian (network order) by default. To parse or build little-endian struct, specify *endian*
option to the struct and use little-endian types::
    
    from namedstruct import nstruct, uint16, uint16_le
    
    struct4 = nstruct((uint16, 'a'),
                    (uint16, 'b'),
                    name = 'struct4',
                    padding = 1)
    
    struct4_le = nstruct((uint16_le, 'a'),
                    (uint16_le, 'b'),
                    name = 'struct4_le',
                    padding = 1,
                    endian = '<')
    
    """
    >>> struct4(a = 1, b = 2)._tobytes()
    b'\x00\x01\x00\x02'
    >>> struct4_le(a = 1, b = 2)._tobytes()
    b'\x01\x00\x02\x00'
    """

The struct is automatically padded to multiplies of *padding* bytes. By default *padding* = 8, means that the struct
is padded to align to 8-bytes (64-bits) boundaries. Set *padding* = 1 to disable padding::

    struct5 = nstruct((uint16, 'a'),
                    (uint8, 'b'),
                    name = 'struct5')
    """
    >>> struct5(a=1,b=2)._tobytes()
    b'\x00\x01\x02\x00\x00\x00\x00\x00'
    >>> len(struct5(a=1,b=2))
    8
    >>> struct5(a=1,b=2)._realsize()
    3
    """
    
    struct5_p2 = nstruct((uint16, 'a'),
                    (uint8, 'b'),
                    name = 'struct5_p2',
                    padding = 2)
    
    """
    >>> struct5_p4(a=1,b=2)._tobytes()
    b'\x00\x01\x02\x00'
    >>> len(struct5_p4(a=1,b=2))
    4
    >>> struct5_p4(a=1,b=2)._realsize()
    3
    """

    struct5_p1 = nstruct((uint16, 'a'),
                    (uint8, 'b'),
                    name = 'struct5_p1',
                    padding = 1)
    
    """
    >>> struct5_p1(a=1,b=2)._tobytes()
    b'\x00\x01\x02'
    >>> len(struct5_p1(a=1,b=2))
    3
    >>> struct5_p1(a=1,b=2)._realsize()
    3
    """

See :py:class:`namedstruct.nstruct` for all valid options.

.. _extensible:

----------------------
Extend defined structs
----------------------

With *size* option, a struct can have more data than the defined fields on parsing. Also it is possible
to let a struct use more data with :py:func:`namedstruct.typedef.create`. Besides using the data for
variable length fields, it is also possible to use the extra data for extending. The extending works like
C/C++ inherits: the fields of base class is parsed first, then the extending fields. Different from C/C++
inherits, the child classe types are automatically determined with *criterias* on parsing::
   
   from namedstruct import *
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

.. _embeddedstruct:

----------------
Embedded structs
----------------
   
An anonymous field has different means when it has different types:

- An anonymous field of primitive type (e.g. uint8, uint16, or uint8[5]) is automatically converted to padding bytes

- An anonymous field of struct type is an embedded struct.

When a struct is embedded into another struct, all the fields of the embedded struct act same as directly defined
in the parent struct. The embedded struct has the same function as normal structs, like **inherit**, **variable length
data**, **padding**, *size* option, and struct size. Parent fields may also be accessed from the embedded struct::
   
   inner_struct = nstruct((uint16[0], 'array'),
                          name = 'inner_struct',
                          padding = 4,
                          size = lambda x: x.arraylength,        # Get size from parent struct
                          prepack = packrealsize('arraylength')  # Pack to parent struct
                          )
   
   parent_struct = nstruct((uint16, 'totallength'),
                           (uint16, 'arraylength'),
                           (inner_struct,),
                           (raw, 'extra'),
                           padding = 1,
                           name = 'parent_struct',
                           size = lambda x: x.arraylength,
                           prepack = lambda: packrealsize('totallength'))

   """
   >>> parent_struct(array = [1,2,3], extra = b'abc')._tobytes()
   b'\x00\x0f\x00\x06\x00\x01\x00\x02\x00\x03\x00\x00abc'
   >>> parent_struct.parse(b'\x00\x0f\x00\x06\x00\x01\x00\x02\x00\x03\x00\x00abc')[0].array
   [1,2,3]
   """

.. _othertypes:

----------------
Other Data Types
----------------

:py:class:`namedstruct.enum` is a way to define C/C++ enumerates. They act like normal primitive types,
but when use :py:func:`nstruct.dump` to generate human readable result, the values are converted
to readable names (or readable name list for *bitwise* enumerates). See :ref:`formatting` for more
details on human readable formatting. See :py:class:`namedstruct.enum` document for usage details.::

   my_enum = enum('my_enum', globals(), uint16,
                  MY_A = 1,
                  MY_B = 2,
                  MY_C = 3)
   
   my_type = nstruct((my_enum, 'type'),
                     name = 'my_type',
                     padding = 1)
   
   """
   >>> dump(my_type(type=MY_A))
   {'_type': '<my_type>', 'type': 'MY_A'}
   """

:py:class:`namedstruct.optional` is a simpler way to define an optional field. It is actually
an small embedded struct, with a criteria to determine whether it should parse the field::
   
   struct1 = nstruct((uint8, 'hasdata'),
                     (optional(uint16, 'data', lambda x: x.hasdata),),
                     name = 'struct1',
                     prepack = packexpr(lambda x: hasattr(x, 'data'), 'hasdata'),
                     padding = 1)
   """
   >>> struct1()._tobytes()
   b'\x00'
   >>> struct1(data=2)._tobytes()
   b'\x01\x00\x02'
   >>> struct1.parse(b'\x01\x00\x02')[0].data
   2
   """

:py:class:`namedstruct.darray` is an array type whose element count is determined by other field. It is another
way to store an array with varaible element count::
   
    from namedstruct import nstruct, uint16, raw, packrealsize, darray
    my_size_struct = nstruct((uint16, 'length'),
                            (raw, 'data'),
                            padding = 1,
                            name = 'my_size_struct',
                            prepack = packrealsize('length'),
                            size = lambda x: x.length)
   
    my_darray_struct = nstruct((uint16, 'arraysize'),
                               (darray(my_size_struct, 'array', lambda x: x.arraysize),),
                               name = 'my_darray_struct',
                               prepack = packexpr(lambda x: len(x.array), 'arraysize'),
                               padding = 1)
    
    """
    >>> my_darray_struct(array = [my_size_struct(data = b'ab'), my_size_struct(data = b'cde')])._tobytes()
    b'\x00\x02\x00\x04ab\x00\x05cde'
    >>> my_darray_struct.parse(b'\x00\x02\x00\x04ab\x00\x05cde')[0].array[1].data
    b'cde'
    """

:py:class:`namedstruct.bitfield` is a mini-struct with bits::
    
    mybit = bitfield(uint64,
                     (4, 'first'),
                     (5, 'second'),
                     (2,),    # Padding bits
                     (19, 'third'),    # Can cross byte border
                     (1, 'array', 20), # A array of 20 1-bit numbers
                     name = 'mybit',
                     init = packvalue(2, 'second'))
    """
    >>> mybit().second
    2
    >>> mybit(first = 5, third = 7)._tobytes()
    b'Q\x00\x00\x1c\x00\x00\x00\x00'         # b'Q' = b'\x51'
    # the uint64 is '0b0101000100000000000000000001110000000000000000000000000000000000'
    """
    
