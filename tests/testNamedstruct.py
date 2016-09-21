'''
Created on 2016/1/19

:author: hubo
'''
from __future__ import print_function
import unittest
from namedstruct import *
from pprint import pprint

bitfield_test = bitfield(uint32,
                         (1, 'a'),
                         (9, 'r'),
                         (11, 'g'),
                         (11, 'b'),
                         name = 'bitfield_test',
                         init = packvalue(1, 'a'))

bitfield_array = bitfield(uint64,
                          (3, 'pre'),
                          (1, 'bits', 50),
                          (4,),
                          (7, 'post'),
                          name = 'bitfield_array'
                          )

pre_enum = enum('pre_enum', globals(), uint8, True,
                PRE_A = 0x1,
                PRE_B = 0x2,
                PRE_C = 0x4
                )

test_struct = nstruct((bitfield_array, 's1'),
                      (bitfield_test[2], 'colors'),
                      (bitfield_array[0], 'extras'),
                      size = sizefromlen(128, 's1', 'post'),
                      prepack = packsize('s1', 'post'),
                      name = 'test_struct',
                      extend = {('s1', 'pre'): pre_enum}
                      )

class Test(unittest.TestCase):
    def testBitfield(self):
        c = bitfield_test.new(a = 0, r = 0x77, g = 0x312, b = 0x57a)
        # 0b00011101110110001001010101111010
        self.assertEqual(bitfield_test.tobytes(c), b'\x1d\xd8\x95\x7a')
        self.assertEqual(dump(c, False), dump(bitfield_test.parse(bitfield_test.tobytes(c))[0], False))
        self.assertEqual(dump(c, False), dump(bitfield_test.create(bitfield_test.tobytes(c)), False))
        c2 = bitfield_test.new()
        self.assertEqual(bitfield_test.tobytes(c2), b'\x80\x00\x00\x00')
        c3 = bitfield_array.new(pre=2, bits = [(r & 1) for r in range(0,50)], post = 0x3f)
        self.assertEqual(c3._tobytes(), b'\x4a\xaa\xaa\xaa\xaa\xaa\xa8\x3f')
        self.assertEqual(dump(c3, False), dump(bitfield_array.parse(bitfield_array.tobytes(c3))[0], False))
        self.assertEqual(dump(c3, False), dump(bitfield_array.create(bitfield_array.tobytes(c3)), False))
        c4 = test_struct.new()
        # 0b0100000000000000000010000000000010000000000000000000000000100000
        c4.s1.pre = 2
        c4.s1.bits[17] = 1
        c4.s1.bits[29] = 1
        # 0b10000010100000000000000000001100
        c4.colors[0].r = 10
        c4.colors[0].b = 12
        # 0b00000000000000000100100000000000
        c4.colors[1].a = 0
        c4.colors[1].g = 9
        c4.extras.append(bitfield_array.new(pre=1, post = 0x1f))
        c4.extras.append(bitfield_array.new(pre=2, bits = [1] * 50, post = 0x17))
        b = c4._tobytes()
        self.assertEqual(b, b'\x40\x00\x08\x00\x80\x00\x00\x20\x82\x80\x00\x0c\x00\x00\x48\x00'\
                         b'\x20\x00\x00\x00\x00\x00\x00\x1f\x5f\xff\xff\xff\xff\xff\xf8\x17')
        self.assertEqual(dump(c4, False), dump(test_struct.parse(b)[0], False))
        self.assertEqual(dump(c4, False), dump(test_struct.create(b), False))
        pprint(dump(test_struct.create(b)))
    def testDarray(self):
        s1 = nstruct((uint8, 'length'),
                     (raw, 'data'),
                     size = lambda x: x.length + 1,
                     prepack = packexpr(lambda x: len(x.data), 'length'),
                     name = 's1',
                     padding = 1
                     )
        s2 = nstruct((uint16, 'size'),
                     (darray(s1, 'strings', lambda x: x.size),),
                     name = 's2',
                     prepack = packexpr(lambda x:len(x.strings), 'size'),
                     padding = 1)
        array = s2()
        array.strings.append(s1(data=b'abc'))
        array.strings.append(s1(data=b'defghi'))
        b = s2.tobytes(array)
        self.assertEqual(b, b'\x00\x02\x03abc\x06defghi')
        array2, size = s2.parse(b)
        self.assertEqual(size, len(b))
        self.assertEqual(dump(array, False), dump(array2, False))
    def testEmptyBase(self):
        s1 = nstruct(name = 's1', padding = 1, classifier = lambda x: x.type)
        s2 = nstruct((uint16, 'a'), base = s1, classifyby = (1,), name = 's2', init = packvalue(1, 'type'))
        s3 = nstruct((uint8,'type'),(s1,),padding = 1, name = 's3', lastextra = True)
        r = s3.create(b'\x01\x00\x02')
        self.assertEqual(r.a, 2)
        self.assertEqual(r._tobytes(), b'\x01\x00\x02')
        s = s3((s1, s2), a = 3)
        self.assertEqual(s._tobytes(), b'\x01\x00\x03')
    def testEmbeddedTypes(self):
        s1 = nstruct(name = 's1', padding = 1, classifier = lambda x: x.type, size = lambda x: 2 if x.type == 1 else 0)
        s2 = nstruct((uint16, 'a'), base = s1, classifyby = (1,), name = 's2', init = packvalue(1, 'type'))
        # Embedded struct
        s3 = nstruct((uint8,'type'),(s1,),padding = 1, name = 's3')
        # Embedded struct in an inherited type
        s4 = nstruct((uint8, 'maintype'), (uint8, 'type'), padding = 1, name = 's4')
        s5 = nstruct((s1,), base = s4, criteria = lambda x: x.maintype == 1, init = packvalue(1, 'maintype'),
                     name = 's5', lastextra = True)
        # Embedded struct in another embedded type
        s6 = nstruct((s1,),padding = 1, name = 's6', inline = False)
        s7 = nstruct((uint8,'type'),(uint8,'type2'),(s6,),padding = 1, name = 's7', lastextra = True)
        # Replace after replace
        s8 = nstruct((uint16, 'b'), base = s6, name = 's8', criteria = lambda x: x.type2 == 3, init = packvalue(3, 'type2'))
        s = s3((s1,s2), a = 3)
        b = s._tobytes()
        self.assertEqual(b, b'\x01\x00\x03')
        self.assertEqual(dump(s3.create(b), False), dump(s, False))
        s = s5((s1,s2), a = 3)
        b = s._tobytes()
        self.assertEqual(b, b'\x01\x01\x00\x03')
        self.assertEqual(dump(s5.create(b), False), dump(s, False))
        s = s7((s1,s2), a = 3)
        b = s._tobytes()
        self.assertEqual(b, b'\x01\x00\x00\x03')
        self.assertEqual(dump(s7.create(b), False), dump(s, False))
        s = s7((s6,s8), (s1,s2), a = 2, b = 6)
        b = s._tobytes()
        self.assertEqual(b, b'\x01\x03\x00\x02\x00\x06')
        self.assertEqual(dump(s7.create(b), False), dump(s, False))
        # _get_embedded
        s = s7()
        b = s._get_embedded(s1)._tobytes()
        self.assertEqual(b, b'')
        s = s7((s1, s2), a = 3)
        b = s._get_embedded(s1)._tobytes()
        self.assertEqual(b, b'\x00\x03')
        b = s._get_embedded(s1)._tobytes(True)
        self.assertEqual(b, b'\x00\x03')
        s = s7((s6,s8), (s1,s2), a = 2, b = 6)
        b = s._get_embedded(s1)._tobytes()
        self.assertEqual(b, b'\x00\x02')
        b = s._get_embedded(s1)._tobytes(True)
        self.assertEqual(b, b'\x00\x02')
    def testVariant(self):
        vtype = enum('vtype', None, uint8,
                     TYPE_A = 1,
                     TYPE_B = 2,
                     TYPE_C = 3)
        v1 = nvariant('v1',
                      nstruct((vtype, 'type'),
                              name = 'v1h',
                              padding = 1),
                      classifier = lambda x: x.type)
        n1 = nstruct((uint32, 'a'), name = 'n1', base = v1, classifyby = (1,), init = packvalue(1, 'type'))
        n2 = nstruct((uint16, 'b'), name = 'n1', base = v1, classifyby = (2,), init = packvalue(2, 'type'))
        n3 = nstruct((uint16, 'sublen'),
                     (uint16, 'subtype'),
                     name = 'n3',
                     base = v1,
                     classifyby = (3,),
                     init = packvalue(3, 'type'),
                     prepack = packrealsize('sublen'),
                     size = lambda x: x.sublen,
                     padding = 1
                     )
        n3_sub1 = nstruct((uint16[0], 'subarray'),
                         name = 'n3_sub1',
                         base = n3,
                         criteria = lambda x: x.subtype == 1,
                         init = packvalue(1, 'subtype'))
        n3_sub2 = nstruct((raw, 'text'),
                         name = 'n3_sub2',
                         base = n3,
                         criteria = lambda x: x.subtype == 2,
                         init = packvalue(2, 'subtype'))
        np_array = nstruct((uint32, 'length'),
                           (v1[0], 'array'),
                           name = 'np_array',
                           padding = 1,
                           size = lambda x: x.length,
                           prepack = packsize('length'))
        s = n1(a = 1)
        b = s._tobytes()
        self.assertEqual(b, b'\x01\x00\x00\x00\x01')
        r = v1.parse(b'\x01\x00')
        self.assertIsNone(r)
        r = v1.parse(b)
        self.assertIsNotNone(r)
        s2, l = r
        self.assertEqual(l, len(b))
        self.assertEqual(s2.a, 1)
        self.assertEqual(dump(s2, typeinfo = DUMPTYPE_NONE), {'type': 'TYPE_A', 'a': 1})
        s = n2(b = 2)
        b = s._tobytes()
        self.assertEqual(b, b'\x02\x00\x02')
        r = v1.parse(b)
        self.assertIsNotNone(r)
        s2, l = r
        self.assertEqual(l, len(b))
        self.assertEqual(s2.b, 2)
        s = n3_sub1(subarray = [1,2,3])
        b = s._tobytes()
        self.assertEqual(b, b'\x03\x00\x0a\x00\x01\x00\x01\x00\x02\x00\x03')
        r = v1.parse(b)
        self.assertIsNotNone(r)
        s2, l = r
        self.assertEqual(l, len(b))
        self.assertEqual(s2.subarray, [1,2,3])
        s = np_array(array = [n1(a = 1), n2(b = 2), n1(a = 3), n3_sub2(text = 'def'), n3_sub1(subarray = [1,2,3])])
        b = s._tobytes()
        self.assertEqual(b, b'\x00\x00\x00\x24\x01\x00\x00\x00\x01\x02\x00\x02\x01\x00\x00\x00\x03\x03\x00\x07\x00\x02def\x03\x00\x0a\x00\x01\x00\x01\x00\x02\x00\x03')
        s2, l = np_array.parse(b)
        self.assertEqual(l, len(b))
        self.assertEqual(s2.array[0].a, 1)
        self.assertEqual(s2.array[1].b, 2)
        self.assertEqual(s2.array[2].a, 3)
        self.assertEqual(s2.array[3].text, 'def')
        self.assertEqual(s2.array[4].subarray, [1,2,3])
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()