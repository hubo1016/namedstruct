.. _tips:

Advanced Examples
=================

The key to create a very complicated dynamic data type is using embedded struct and extended struct wisely.
An embedded struct can access fields of parent struct and keep its own characteristics at the same time;
An extended struct can access fields of the base struct and also inherits the characteristics of the base type.

------------------------------------------------
Struct with More Than One Variable Length Fields
------------------------------------------------

Use embedded struct to control the variable length fields (a simplied version of ARP packet with some fields removed)::

   from namedstruct import *
   
   _arp_hw_src = nstruct((raw, 'hw_src'),
                         size = lambda x: x.hw_length,
                         prepack = packrealsize('hw_length'),
                         name = '_arp_hw_src')

   _arp_hw_dst = nstruct((raw, 'hw_dst'),
                         size = lambda x: x.hw_length,
                         name = '_arp_hw_dst')

   _arp_nw_src = nstruct((raw, 'nw_src'),
                         size = lambda x: x.nw_length,
                         prepack = packrealsize('nw_length'),
                         name = '_arp_nw_src')

   _arp_nw_dst = nstruct((raw, 'nw_dst'),
                         size = lambda x: x.nw_length,
                         name = '_arp_nw_dst')
   
   arp = nstruct((uint16, 'hw_length'),
                  (uint16, 'nw_length'),
                  (_arp_hw_src,),
                  (_arp_nw_src,),
                  (_arp_hw_dst,),
                  (_arp_nw_dst,),
                  name = 'arp',
                  padding = 1
                  )
   
   """
   >>> arp(hw_src = b'\x00\xff\x01\x3f\x11\x1b', hw_dst = b'\x00\xff\x08\x7e\x10\x0a', nw_src = b'\xc0\xa8\x01\x02',
           nw_dst = b'\xc0\xa8\x01\x03')._tobytes()
   b'\x00\x06\x00\x04\x00\xff\x01?\x11\x1b\xc0\xa8\x01\x02\x00\xff\x08~\x10\n\xc0\xa8\x01\x03'
   >>> dump(arp.parse(b'\x00\x03\x00\x01\x00\xff\xaa\x00\xff\xbb\x17\x19')[0])
   {'_type': '<arp>', 'nw_length': 1, 'nw_dst': '\x19', 'hw_src': '\x00\xff\xaa', 'nw_src': '\x00', 'hw_dst': '\xff\xbb\x17', 'hw_length': 3}
   """

The length of *hw_src*, *hw_dst*, *nw_src*, *nw_dst* fields are determined by *hw_length* and *nw_length*. It is also
possible to define the embedded struct inside the main struct::

   arp = nstruct((uint16, 'hw_length'),
              (uint16, 'nw_length'),
              (nstruct((raw, 'hw_src'),
                   size = lambda x: x.hw_length,
                   name = '_arp_hw_src',
                   prepack = packrealsize('hw_length'),
                   padding = 1),),
              (nstruct((raw, 'nw_src'),
                   size = lambda x: x.nw_length,
                   name = '_arp_nw_src',
                   prepack = packrealsize('nw_length'),
                   padding = 1),),
              (nstruct((raw, 'hw_dst'),
                   size = lambda x: x.hw_length,
                   name = '_arp_hw_dst',
                   padding = 1),),
              (nstruct((raw, 'nw_dst'),
                   size = lambda x: x.nw_length,
                   name = '_arp_nw_dst',
                   padding = 1),),
              name = 'arp',
              padding = 1
              )


-------------------------
Extend an Embedded Struct
-------------------------

An embedded struct can also be extended (inherited) (a simplied version of ARP packet with l2 header and some fields removed)::
   
   from namedstruct import *
   
   ETH_ALEN = 6
   mac_addr = uint8[ETH_ALEN]
   mac_addr.formatter = lambda x: ':'.join('%02X' % (n,) for n in x)
   
   ether_l2 = nstruct((mac_addr, 'dmac'),
                      (mac_addr, 'smac'),
                      (uint16, 'ethertype'),
                      name = 'ether_l2',
                      padding = 1,
                      size = lambda x: 18 if x.ethertype == 0x8100 else 14)
   
   ether_l2_8021q = nstruct((bitfield(uint16,
                                    (3, 'pri'),
                                    (1, 'cfi'),
                                    (12, 'tag')),),
                            (uint16, 'ethertype2'),
                            base = ether_l2,
                            criteria = lambda x: x.ethertype == 0x8100,
                            init = packvalue(0x8100, 'ethertype'))
   
   ether_l3 = nstruct((ether_l2,),
                      name = 'ether_l3',
                      padding = 1,
                      classifier = lambda x: getattr(x, 'ethertype2', x.ethertype))
   
   arp = nstruct((uint16, 'hw_length'),
              (uint16, 'nw_length'),
              (nstruct((raw, 'hw_src'),
                   size = lambda x: x.hw_length,
                   name = '_arp_hw_src',
                   prepack = packrealsize('hw_length'),
                   padding = 1),),
              (nstruct((raw, 'nw_src'),
                   size = lambda x: x.nw_length,
                   name = '_arp_nw_src',
                   prepack = packrealsize('nw_length'),
                   padding = 1),),
              (nstruct((raw, 'hw_dst'),
                   size = lambda x: x.hw_length,
                   name = '_arp_hw_dst',
                   padding = 1),),
              (nstruct((raw, 'nw_dst'),
                   size = lambda x: x.nw_length,
                   name = '_arp_nw_dst',
                   padding = 1),),
              name = 'arp',
              padding = 1
              )
   
   ether_l3_arp = nstruct((arp,),
                          name = 'ether_l3_arp',
                          base = ether_l3,
                          classifyby = (0x0806,),
                          init = packvalue(0x0806, 'ethertype'))
   
   """
   # Create a packet without VLAN tag
   >>> ether_l3_arp(dmac = [0x00, 0xff, 0x1a, 0x1b, 0x1c, 0x1d],
                    smac = [0x00, 0xff, 0x0a, 0x0b, 0x0c, 0x0d],
                    hw_src = b'\x00\xff\x0a\x0b\x0c\x0d',
                    hw_dst = b'\x00\xff\x1a\x1b\x1c\x1d',
                    nw_src = b'\xc0\xa8\x01\x02',
                    nw_dst = b'\xc0\xa8\x01\x03')._tobytes()
   b'\x00\xff\x1a\x1b\x1c\x1d\x00\xff\n\x0b\x0c\r\x08\x06\x00\x06\x00\x04\x00\xff\n\x0b\x0c\r\xc0\xa8\x01\x02\x00\xff\x1a\x1b\x1c\x1d\xc0\xa8\x01\x03'
   
   # Create a packet with VLAN tag
   >>> ether_l3_arp((ether_l2, ether_l2_8021q),
                     dmac = [0x00, 0xff, 0x1a, 0x1b, 0x1c, 0x1d],
                     smac = [0x00, 0xff, 0x0a, 0x0b, 0x0c, 0x0d],
                     hw_src = b'\x00\xff\x0a\x0b\x0c\x0d',
                     hw_dst = b'\x00\xff\x1a\x1b\x1c\x1d',
                     nw_src = b'\xc0\xa8\x01\x02',
                     nw_dst = b'\xc0\xa8\x01\x03',
                     tag = 100,
                     ethertype2 = 0x0806)._tobytes()
   b'\x00\xff\x1a\x1b\x1c\x1d\x00\xff\n\x0b\x0c\r\x81\x00\x00d\x08\x06\x00\x06\x00\x04\x00\xff\n\x0b\x0c\r\xc0\xa8\x01\x02\x00\xff\x1a\x1b\x1c\x1d\xc0\xa8\x01\x03'
   
   # Parse a packet without VLAN tag
   >>> dump(ether_l3.create(b'\x00\xff\x1a\x1b\x1c\x1d\x00\xff\n\x0b\x0c\r\x08\x06\x00\x06\x00\x04\x00\xff\n\x0b\x0c\r\xc0\xa8\x01\x02\x00\xff\x1a\x1b\x1c\x1d\xc0\xa8\x01\x03'))
   {'dmac': '00:FF:1A:1B:1C:1D', '_type': '<ether_l3_arp>', 'nw_length': 4, 'nw_dst': '\xc0\xa8\x01\x03', 'ethertype': 2054, 'smac': '00:FF:0A:0B:0C:0D', 'hw_src': '\x00\xff\n\x0b\x0c\r', 'nw_src': '\xc0\xa8\x01\x02', 'hw_dst': '\x00\xff\x1a\x1b\x1c\x1d', 'hw_length': 6}   """
   
   # Parse a packet with VLAN tag
   >>> dump(ether_l3.create(b'\x00\xff\x1a\x1b\x1c\x1d\x00\xff\n\x0b\x0c\r\x81\x00\x00d\x08\x06\x00\x06\x00\x04\x00\xff\n\x0b\x0c\r\xc0\xa8\x01\x02\x00\xff\x1a\x1b\x1c\x1d\xc0\xa8\x01\x03'))
   {'dmac': '00:FF:1A:1B:1C:1D', '_type': '<ether_l3_arp>', 'nw_length': 4, 'nw_dst': '\xc0\xa8\x01\x03', 'ethertype': 33024, 'cfi': 0, 'pri': 0, 'smac': '00:FF:0A:0B:0C:0D', 'hw_src': '\x00\xff\n\x0b\x0c\r', 'tag': 100, 'ethertype2': 2054, 'nw_src': '\xc0\xa8\x01\x02', 'hw_dst': '\x00\xff\x1a\x1b\x1c\x1d', 'hw_length': 6}   
   """
