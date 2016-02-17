.. _formatting:

Formatting
==========

One of the important functions of *namedstruct* library is the ability to convert
a binary struct into human readable format. The library does not convert the struct
directly into strings. Instead, it converts the struct into dictionaries and lists,
which is suitable for *pprint* or *json.dumps* as well as further processing.
Call :py:func:`namedstruct.dump` on a parsed value to convert it into this format::

   from namedstruct import *
   
   my_struct = nstruct((uint16, 'x'),
                       (uint8, 'y'),
                       (raw, 'data'),
                       padding = 1,
                       name = 'my_struct')
   s = my_struct(x = 1, y = 2, data = b'abc')
   """
   >>> dump(s)
   {'y': 2, 'x': 1, '_type': '<my_struct>', 'data': 'abc'}
   >>> dump(s, typeinfo = DUMPTYPE_NONE)
   {'y': 2, 'x': 1, 'data': 'abc'}
   """
   
.. _humanreadable:

-------------------------
Human Readable Formatting
-------------------------

There are different options on calling :py:func:`namedstruct.dump`. When *humanread* is True,
extra formatting procedures are executed on special data types to convert them into human-readable
format. For example, enumerates defined by :py:class:`namedstruct.enum` are converted into names::

   from namedstruct import *
   
   gender = enum('gender', globals(),uint8,
                  MALE = 0,
                  FEMALE = 1)
   
   abilities = enum('abilities', globals(), uint16, True,
                     SWIMMING = 1<<0,
                     JUMPING = 1<<1,
                     RUNNING = 1<<2,
                     CLIMBING = 1<<3)
   
   person = nstruct((cstr, 'name'),
                     (gender, 'gender'),
                     (abilities, 'abilities'),
                     name = 'person',
                     padding = 1)
   
   john = person(name = 'john', gender = MALE, abilities = JUMPING | CLIMBING)
   
   """
   >>> dump(john, True)
   {'gender': 'MALE', '_type': '<person>', 'abilities': 'JUMPING CLIMBING', 'name': 'john'}
   >>> dump(john, False)
   {'gender': 0, '_type': '<person>', 'abilities': 10, 'name': 'john'}
   """

See :py:func:`namedstruct.dump` for descriptions of parameters.

.. _customizedformatting:

------------------------------------
Customized Human Readable Formatting
------------------------------------

There are three approaches to customize the display format of a data type when calling
:py:func:`namedstruct.dump`.

- Formatter Attribute
  
  Set the *formatter* attribute of a defined data type to a function to execute it on formatting.
  The function should take the "unformatted" representation of the data as a parameter, and return
  the formatted data::
  
      ETH_ALEN = 6
      mac_addr = uint8[ETH_ALEN]
      mac_addr.formatter = lambda x: ':'.join('%02X' % (n,) for n in x)
      
      my_packet = nstruct((mac_addr, 'src'),
                           (mac_addr, 'dst'),
                           name = 'my_packet',
                           padding = 1)
      
      
      p = my_packet(src = [0x00, 0xFF, 0x31, 0x14, 0x25, 0x17], dst = [0x00, 0xFF, 0x12, 0x45, 0x7a, 0x0b])
      """
      >>> dump(p, False)
      {'src': [0, 255, 49, 20, 37, 23], 'dst': [0, 255, 18, 69, 122, 11], '_type': '<my_packet>'}
      >>> dump(p)
      {'src': '00:FF:31:14:25:17', 'dst': '00:FF:12:45:7A:0B', '_type': '<my_packet>'}
      """
      
  Notice that the *formatter* attribute of the data type only has effect when the data type is used as
  the type of a field in a struct.
  
- Formatter Option
  
  :py:class:`namedstruct.nstruct` has a *formatter* option, which is similar to the *formatter* attribute.
  Different from setting the attribute, the option is executed even if the data type is the out-most
  struct::
  
      ops = ['+', '-', '*', '/']
      
      expr = nstruct((uint32, 'a'),
                     (uint32, 'b'),
                     (uint8, 'op'),
                     name = 'expr',
                     padding = 1,
                     formatter = lambda x: '%d %s %d' % (x['a'], ops[x['op']], x['b']))
      
      """
      >>> dump(expr(a = 12, b = 23, op = 0))
      '12 + 23'
      """
      
- Type Extending
  
  Sometimes it is not possible to know the exact format of a field in a struct until the struct is subclassed.
  *extend* option can be used to replace the formatting procedure of a field as if the field is in type defined
  by *extend* option::
      
      from namedstruct import *
      
      person_type = enum('person_type', globals(), uint8,
                        STUDENT = 0,
                        TEACHER = 1)
      
      student_flag = enum('student_flag', globals(), uint8, True,
                           HARDWORKING = 1<<0,
                           SMART = 1<<1,
                           FRIENDLY = 1<<2,
                           STRONG = 1<<3)
      
      teacher_flag = enum('teacher_flag', globals(), uint8, True,
                           HARDWORKING = 1<<0,
                           EXPERIENCED = 1<<1,
                           ENTHUSIASTIC = 1<<2,
                           STRICT = 1<<3)
      
      person = nstruct((uint16, 'length'),
                        (person_type, 'type'),
                        (uint8, 'flag'),
                        classifier = lambda x: x.type,
                        name = 'person',
                        padding = 1,
                        size = lambda x: x.length,
                        prepack = packrealsize('length'))
      
      student = nstruct((uint8, 'grade'),
                        (uint8, 'classno'),
                        name = 'student',
                        classifyby = (STUDENT,),
                        init = packvalue(STUDENT, 'type'),
                        extend = {'flag': student_flag},
                        base = person)
                           
      teacher = nstruct((uint8, 'age'),
                        (uint8, 'subject'),
                        name = 'teacher',
                        classifyby = (TEACHER,),
                        init = packvalue(TEACHER, 'type'),
                        extend = {'flag': teacher_flag},
                        base = person)
      
      """
      >>> dump(student(grade = 2, classno = 1, flag = 10))
      {'_type': '<student>', 'grade': 2, 'length': 0, 'flag': 'SMART STRONG', 'classno': 1, 'type': 'STUDENT'}
      >>> dump(teacher(age = 35, subject = 0, flag = 10))
      {'_type': '<teacher>', 'age': 35, 'flag': 'EXPERIENCED STRICT', 'length': 0, 'type': 'TEACHER', 'subject': 0}
      """

The overall formatting procedure of a struct is in this order:

1. Dump result of every field (including fields of base type, fields of embedded structs) is calculated.
   If the field value is a struct, the struct formatting is the same as this procedure.

2. Fields defined in this struct (including fields of base type, excluding fields of embedded structs)
   is formatted with the "formatter", either from the original type or from the *extend* type. If any
   descendant fields are extended with *extend*, they are also formatted.

3. Embedded structs are formatted like in 2 i.e. fields with "formatter" and fields in *extend* are
   formatted.

4. *formatter* option is executed if it is defined in the struct type.
