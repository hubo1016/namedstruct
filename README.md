# namedstruct
Define complicated C/C++ structs in Python with variable length arrays, header/extend relations, extensible structures in one time, parse/rebuild them with a single line of code

This library is designed for Openflow structures parsing in VLCP (https://github.com/hubo1016/vlcp) project.
It is also used 

The documents are still in-progress, see docstring in namedstruct.namedstruct for details.

Some examples are given in *misc* package, including a complete definition of Openflow 1.0, 1.3 and Nicira
extensions. They are not part of the library but can be used freely. The Openflow structures are very
complicated C/C++ structures, usually you will need more than 6000 lines of **hard-coded, not extensible,
uneasy to maintain** Python code to parse them. With *namedstruct*, I just modified the openflow.h, nicira_ext.h
headers with some rules and created the types in **several days**. I even keep the license and remarks unchanged.

Another example parses GZIP file header, which is a little-endian format. It is used in HTTP implementation in VLCP
to extract the deflate data from a GZIP-encoded content without creating a in-memory file. 
