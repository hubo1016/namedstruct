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

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()