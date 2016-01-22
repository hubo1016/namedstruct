'''
Created on 2016/1/22

:author: hubo
'''
from __future__ import print_function
from namedstruct import *
from timeit import timeit
import struct

mystruct = nstruct((uint16, 'a'),
                   (uint8, 'b'),
                   (uint32, 'c'),
                   (uint8,),
                   (uint8[4], 'd'),
                   (char[4], 'e'),
                   name = 'mystruct'
                   )

class MyObject(object):
    pass

s = struct.Struct('>HBIx4B4s')

def parse(b):
    v = s.unpack_from(b)
    r = MyObject()
    r.a = v[0]
    r.b = v[1]
    r.c = v[2]
    r.d = list(v[3:7])
    r.e = v[7]
    return r

def pack(o):
    arglist = [o.a, o.b, o.c]
    arglist.extend(o.d)
    arglist.append(o.e)
    return s.pack(*arglist)


mystruct2 = nstruct((uint16, 'length'),
                    (uint8, 'type'),
                    (uint8,),
                    name = 'mystruct2',
                    size = lambda x: x.length,
                    prepack = packrealsize('length'),
                    padding = 4
                    )

mystruct2_1 = nstruct((raw, 'content'),
                      base = mystruct2,
                      criteria = lambda x: x.type == 1,
                      init = packvalue(1, 'type'),
                      name = 'mystruct2_1'
                      )

mystruct2_2 = nstruct((uint16, 'content'),
                      (uint16, 'othercontent'),
                      base = mystruct2,
                      criteria = lambda x: x.type == 2,
                      init = packvalue(2, 'type'),
                      name = 'mystruct2_2'
                      )

s2 = struct.Struct('>HBx')

s2_2 = struct.Struct('>HH')

def parse2(b):
    (l, t) = s2.unpack_from(b)
    r = MyObject
    r.length = l
    r.type = t
    if t == 1:
        r.content = b[s2.size:l]
    elif t == 2:
        r.content, r.othercontent = s2_2.unpack_from(b[s2.size:])
    return r

def pack2(r):
    if r.type == 1:
        r.length = len(r.content) + s2.size
        return s2.pack(r.length, r.type) + r.content
    elif r.type == 2:
        return s2.pack(r.length, r.type) + s2_2.pack(r.content, r.othercontent)

if __name__ == '__main__':
    b = mystruct(a=12, b=3, c=19, d = [1,2,3,4], e = b'abcd')._tobytes()
    print('mystruct.parse * 1000000:')
    print(timeit(lambda: mystruct.parse(b)))
    print('Struct.unpack * 1000000:')
    print(timeit(lambda: parse(b)))
    m1 = mystruct(a = 7, b = 2, c = 17, d = [3,4,5,6], e = b'1234')
    print('mystruct._tobytes * 1000000:')
    print(timeit(lambda: m1._tobytes()))
    mo1 = MyObject()
    mo1.a = 7
    mo1.b = 2
    mo1.c = 17
    mo1.d = [3,4,5,6]
    mo1.e = b'1234'
    print('Struct.pack * 1000000:')
    print(timeit(lambda: pack(mo1)))
    b2_1 = mystruct2_1(content = b'123456')._tobytes()
    b2_2 = mystruct2_2(content = 12, othercontent = 34)._tobytes()
    print('mystruct2_1.parse + mystruct2_2.parse * 500000:')
    print(timeit(lambda: (mystruct2.parse(b2_1), mystruct2.parse(b2_2)), number = 500000))
    print('unpack2_1 + unpack2_2 * 500000:')
    print(timeit(lambda: (parse2(b2_1), parse2(b2_2)), number = 500000))
    m2_1 = mystruct2_1(content = b'123456')
    m2_2 = mystruct2_2(content = 12, othercontent = 34)
    mo2_1 = MyObject()
    mo2_1.type = 1
    mo2_1.content = b'123456'
    mo2_2 = MyObject()
    mo2_2.type = 2
    mo2_2.content = 12
    mo2_2.othercontent = 34
    print('mystruct2_1._tobytes + mystruct2_2._tobytes * 500000:')
    print(timeit(lambda: (m2_1._tobytes(), m2_2._tobytes()), number = 500000))
    print('pack2_1 + pack2_2 * 500000:')
    print(timeit(lambda: (pack2(mo2_1), pack2(mo2_2)), number = 500000))
    