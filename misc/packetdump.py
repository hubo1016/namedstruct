'''
Created on 2016/5/18

:author: hubo
'''
from __future__ import print_function
from pprint import pprint
import socket
import ethernet
import sys
import argparse


def _str(v):
    if isinstance(v, str):
        return v
    elif isinstance(v, bytes):
        return v.decode('ascii')
    else:
        return str(v)

def _str2(v):
    if isinstance(v, str):
        try:
            v.decode('ascii')
        except Exception:
            return repr(v)
        else:
            return v
    elif isinstance(v, bytes):
        try:
            return v.decode('ascii')
        except Exception:
            return repr(v)
        else:
            return v
    else:
        return str(v)


def _format_multilines(v, ljust_len):
    screen_width = max(80 - ljust_len, 16)
    lines = []
    for l in v.splitlines():
        for i in range(0, len(l), screen_width):
            lines.append(l[i:i+screen_width])
    if not lines:
        return ''
    else:
        return '\n'.join([lines[0]] + [' ' * ljust_len + l for l in lines[1:]])

def format_table(x):
    ljust_len = (max(max(len(k) for k in x) + 2, 12) + 3) // 4 * 4
    for k,v in x.items():
        print((k + ':').ljust(ljust_len), _format_multilines(_str2(v), ljust_len + 1))
    print()

def format_pprint(x):
    pprint(x)

import json
def format_json(x):
    print(json.dumps(x, indent=1))

predefined_protocols = {'ip': ethernet.ETHERTYPE_IP,
                        'ip6': ethernet.ETHERTYPE_IPV6,
                        'arp': ethernet.ETHERTYPE_ARP,
                        'all': 0x0003}

predefined_formats = {'table': format_table,
                      'pprint': format_pprint,
                      'json': format_json}

SIOCGIFINDEX = 0x8933
PACKET_ADD_MEMBERSHIP = 1
PACKET_MR_PROMISC = 1
SOL_PACKET = 263

import datetime

def current_timestamp():
    return datetime.datetime.now().strftime('%H:%I:%S.%f')

defined_columns = ('svlan_tci', 'dl_type3', 'vlan_tci', 'dl_type2', 'arp_op', 'arp_sha', 'arp_spa', 'arp_tha', 'arp_tpa',
                   'ip_src', 'ip_dst', 'proto', 'total_len', 'frag_off', 'sport', 'dport', 'seq', 'ack', 'tcp_win', 'tcp_flags',
                   'icmp_type', 'icmp_code', 'icmp_id', 'icmp_seq'
                   )

defined_level = {2: (lambda x,l: ethernet.ethernet_l2.create(x[:l])),
                 3: (lambda x,l: ethernet.ethernet_l3.create(x[:l])),
                 4: (lambda x,l: ethernet.ethernet_l4.create(x[:l])),
                 7: (lambda x,l: ethernet.ethernet_l7.create(x))}

from namedstruct import dump

def create_desp(pd):
    return b', '.join(c + ': ' + _str2(pd[c]) for c in defined_columns if c in pd)

def format_packet(pd, verbose, addr):
    if addr[2] == 4:
        print(current_timestamp(), '{0} - {dl_src} > {dl_dst}, {dl_type}'.format(*addr, **pd), create_desp(pd))
    else:
        print(current_timestamp(), '{0} - {dl_dst} < {dl_src}, {dl_type}'.format(*addr, **pd), create_desp(pd))
    if verbose:
        verbose(pd)

import re

try:
    _long = long
except:
    _long = int

def _contains(lv, rv):
    if isinstance(lv, int) or isinstance(lv, _long):
        return lv & rv
    else:
        return rv in lv

predefined_compare = {'=': lambda a,b: a == b,
                      '!=': lambda a,b: a != b,
                      '<': lambda a,b: a < b,
                      '>': lambda a,b: a > b,
                      '<=': lambda a,b: a <= b,
                      '>=': lambda a,b: a >= b}

def auto_compare(leftvalue, rightvalue, operator):
    def comp(x):
        try:
            lv = x[leftvalue]
        except Exception:
            return False
        if isinstance(lv, int) or isinstance(lv, _long):
            try:
                rv = int(rightvalue)
            except Exception:
                try:
                    rv = getattr(ethernet, rightvalue)
                except Exception:
                    return operator(_str(lv), rightvalue)
                else:
                    if isinstance(rv, int) or isinstance(rv, _long):
                        return operator(lv, rv)
                    else:
                        return operator(_str(lv), rightvalue)
            else:
                return operator(lv, rv)
        else:
            return operator(_str(lv), rightvalue)
    return comp

predefined_reg = {'~': lambda a,b: b.search(_str(a)),
                  '!~': lambda a,b: not b.search(_str(a))}

def auto_reg(leftvalue, rightvalue, operator):
    rr = re.compile(rightvalue)
    def comp(x):
        try:
            lv = x[leftvalue]
        except Exception:
            return False
        return operator(lv, rr)
    return comp
    

_filter_reg = re.compile(r'^([_a-zA-Z0-9]+)\s*(=|!=|<|>|<=|>=|~|!~)\s*(.*)$')

def create_filter(f):
    f = f.strip()
    m = _filter_reg.match(f)
    if not m:
        raise ValueError('%r is not a valid filter expression.' % (f,))
    leftvalue, op, rightvalue = m.groups()
    if op in predefined_compare:
        return auto_compare(leftvalue, rightvalue, predefined_compare[op])
    elif op in predefined_reg:
        return auto_reg(leftvalue, rightvalue, predefined_reg[op])
    else:
        raise ValueError('Unrecognized operator %r' % (op,))
        

if __name__ == '__main__':
    try:
        parse = argparse.ArgumentParser(description='Capture raw packet and display')
        parse.add_argument('-i', '--interface', help='Connect to specified network interface')
        parse.add_argument('-v', '--verbose', action="store_true", help='Show more details of the packet')
        group = parse.add_mutually_exclusive_group()
        group.add_argument('-2', action="store_const", help='Parse only L2(Ethernet)', const = 2, dest = 'level')
        group.add_argument('-3', action="store_const", help='Parse only L3(ARP/IP)', const = 3, dest = 'level')
        group.add_argument('-4', action="store_const", help='Parse only L4(TCP/UDP/ICMP)', const = 4, dest = 'level')
        group.add_argument('-7', action="store_const", help='Parse the full packet including all data', const = 7, dest = 'level')
        parse.add_argument('-l', '--length', type=int, help='Capture packet size limit', default=128)
        parse.add_argument('-p', '--protocol', help='Capture only specified type, valid types are ip/ip6/arp/all/(number)', default="all")
        parse.add_argument('-f', '--format', help='Detail format, table/json/pprint', default='table')
        parse.add_argument('filter', nargs='*', help='Filters like \"dl_src=00:01:02:03:04:05\". Support operaters are: =, !=, <, >, <=, >=, ~, !~ each stands for '\
                           ' equal, not equal, not equal, less, greater, less equal, greater equal, match regexp, not match regexp.')
        args = parse.parse_args()
        if not hasattr(socket, 'AF_PACKET'):
            print("Current operating system does not support AF_PACKET. Try other operating system (e.g. Linux). ", file=sys.stderr)
            sys.exit(1)
        if args.protocol in predefined_protocols:
            protocol = predefined_protocols[args.protocol]
        elif ethernet.ethertype.getValue(args.protocol) is not None:
            protocol = ethernet.ethertype.getValue(args.protocol)
        else:
            protocol = int(args.protocol)
        raw_socket = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(protocol))
        if args.interface:
            raw_socket.bind((args.interface, protocol))
            from fcntl import ioctl
            from ctypes import create_string_buffer
            ifreq = create_string_buffer(args.interface.encode('ascii'), 32)
            if(ioctl(raw_socket.fileno(), SIOCGIFINDEX, ifreq, True) < 0):
                raise OSError('Call ioctl failed')
            import struct
            ifindex = struct.unpack_from('i', ifreq, 16)[0]
            raw_socket.setsockopt(SOL_PACKET, PACKET_ADD_MEMBERSHIP, struct.pack('iHH8s', ifindex, PACKET_MR_PROMISC, 0, b''))
        level = args.level
        if not level:
            level = 4
        parser = defined_level[level]
        if args.verbose:
            verbose = predefined_formats.get(args.format, format_pprint)
        else:
            verbose = None
        length = args.length
        if length <= 14:
            length = 14
        filters = [create_filter(f) for f in args.filter]
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        exit(2)
    try:
        total_packet = 0
        filtered_packet = 0
        while True:
            data, addr = raw_socket.recvfrom(4096)
            try:
                p = parser(data, length)
                pd = dump(p)
            except Exception:
                print('%s Unrecognized packet: %r' % (current_timestamp(), data[:28],))
            else:
                try:
                    total_packet += 1
                    if all(f(pd) for f in filters):
                        filtered_packet += 1
                        format_packet(pd, verbose, addr)
                except Exception as exc:
                    print(str(exc), file=sys.stderr)
    except (KeyboardInterrupt, SystemExit):
        print()
        print("%d/%d packet captured" % (filtered_packet, total_packet))

