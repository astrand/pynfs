#!/usr/bin/env python2

# rpcgen.py - A Python RPC protocol compiler
# 
# Written by Peter Åstrand <peter@cendio.se>
# Copyright (C) 2001 Cendio Systems AB (http://www.cendio.se)
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License. 
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

#
# Note <something>_list means zero or more of <something>.
#
# TODO:
# Replace MemFile with StringIO. 
# Code generation for programs and procedures. 
# __repr__ with discriminants should print symbolic values.
# Add rpcgen info and date to output files. 

import sys
import keyword

#
# Section: Lexical analysis
#

# Note: INT is not mentioned in RFC1832 as a reserved word. Why?
reserved = ("INT", "BOOL", "CASE", "CONST", "DEFAULT", "DOUBLE", "QUADRUPLE",
            "ENUM", "FLOAT", "HYPER", "OPAQUE", "STRING", "STRUCT",
            "SWITCH", "TYPEDEF", "UNION", "UNSIGNED", "VOID",
            # RPC specific
            "PROGRAM", "VERSION")

reserved_map = { }
for r in reserved:
    reserved_map[r.lower()] = r

tokens = reserved + (
    "ID", "NUMBER",
    # ( ) [ ] { } 
    "LPAREN", "RPAREN", "LBRACKET", "RBRACKET", "LBRACE", "RBRACE",
    # ; : < > * = ,
    "SEMI", "COLON", "LT", "GT", "STAR", "EQUALS", "COMMA"
    )

t_ignore = " \t"

def t_ID(t):
    r'[A-Za-z][A-Za-z0-9_]*'
    t.type = reserved_map.get(t.value, "ID")
    return t

def t_NUMBER(t):
    r'(0x[0-9a-fA-F]+)|(0[0-7]+)|(\d+)'
    return t

# Tokens
t_LPAREN           = r'\('
t_RPAREN           = r'\)'
t_LBRACKET         = r'\['
t_RBRACKET         = r'\]'
t_LBRACE           = r'\{'
t_RBRACE           = r'\}'
t_SEMI             = r';'
t_COLON            = r':'
t_LT               = r'<'
t_GT               = r'>'
t_STAR             = r'\*'
t_EQUALS           = r'='
t_COMMA            = r','

def t_newline(t):
    r'\n+'
    t.lineno += t.value.count("\n")

def t_mod(t):
    r'%.*\n'
    t.lineno += 1

# Comments
def t_comment(t):
    r' /\*(.|\n)*?\*/'
    t.lineno += t.value.count('\n')

def t_error(t):
    print "Illegal character %s at %d type %s" % (repr(t.value[0]), t.lineno, t.type)
    t.skip(1)
    
# Build the lexer
import lex
lex.lex(debug=0)

#
# Section: Helper classes and functions. 
#

# Global variablers
known_basics = {"int" : "pack_int",
                "enum" : "pack_enum", 
                "unsigned_int" : "pack_uint",
                "unsigned" : "pack_uint",
                "hyper" : "pack_hyper",
                "unsigned_hyper" : "pack_uhyper",
                "float" : "pack_float",
                "double" : "pack_double",
                # Note: xdrlib.py does not have a
                # pack_quadruple currently. 
                "quadruple" : "pack_double", 
                "bool" : "pack_bool",
                "opaque": "pack_opaque",
                "string": "pack_string"}


known_types = {}


typesheader = """
from nfs4constants import *
from nfs4packer import *

def init_type_class(klass, ncl):
    # Initilize type class
    klass.ncl = ncl
    klass.packer = ncl.packer
    klass.unpacker = ncl.unpacker

def assert_not_none(klass, *args):
    for arg in args:
	if arg == None:
	    raise TypeError(repr(klass) + " has uninitialized data")

def pack_objarray(ncl, list):
    # FIXME: Support for length assertion. 
    ncl.packer.pack_uint(len(list))
    for item in list:
	item.pack()

def unpack_objarray(ncl, klass):
    n = ncl.unpacker.unpack_uint()
    list = []
    for i in range(n):
	obj = klass(ncl)
	obj.unpack()
	list.append(obj)
    return list


# All NFS errors are subclasses of NFSException
class NFSException(Exception):
	pass

class BadDiscriminant(NFSException):
    def __init__(self, value):
        self.value = value

"""


packerheader = """
import rpc
from nfs4types import *

"""


def check_not_reserved(*args):
    for arg in args:
        if keyword.iskeyword(arg):
            raise "Invalid identifier %s is a reserved word" % str(arg)


class IndentPrinter:
    def __init__(self, writer):
        self.indent = 0
        self.writer = writer

    def change(self, indentchange):
        self.indent += indentchange

    def pr(self, *args):
        self._print(args)
        self.writer.write("\n")

    def prcomma(self, *args):
        self._print(args)

    def _print(self, args):
        self.writer.write(" " * self.indent)
        for arg in args:
            self.writer.write(arg)

    def cont(self, *args):
        for arg in args:
            self.writer.write(arg)


class MemFile:
    def __init__(self):
        self.data = ""
    
    def write(self, data):
        self.data += str(data)

    def get_data(self):
        return self.data
        
        
class RPCType:
    # Note: The name is not part of this object.
    def __init__(self, base_type=None,
                 vararray=None, fixarray=None, arraylen=None, isarray=0,
                 void=0, composite=0):
        # Base type. 
        self.base_type = base_type
        # 1 if this is an vector with variabel length. 
        self.vararray = vararray
        # 1 if this is an vector with fixed length. 
        self.fixarray = fixarray
        # Vector length. Vectors with infinite (=2**32-1) length have None. 
        self.arraylen = arraylen
        # 1 if this is an true array. Note: string and opaque type
        # does not count as arrays, but they uses vararray, fixarray
        # and arraylen fields.
        self.isarray = isarray
        # Void?
        self.void = void
        # A composite type is a type with several components (eg. Union or Struct)
        # They are represented by a class in this framework. 
        self.composite = composite

    def array_string(self):
        if self.arraylen:
            lenstring = str(self.arraylen)
        else:
            lenstring = ""
            
        if self.vararray:
            return "<%s>" % lenstring
        elif self.fixarray:
            return "[%s]" % lenstring
        else:
            return ""


class RPCunion_body:
    def __init__(self, declaration=None, switch_body=None):
        self.declaration = declaration
        self.switch_body = switch_body


class RPCswitch_body:
    def __init__(self, first_declaration=None, case_list=None, default_declaration=None):
        self.first_declaration = first_declaration
        self.case_list = case_list # No class, just list of declarations. 
        self.default_declaration = default_declaration


class RPCcase_declaration:
    def __init__(self, value=None, declaration=None):
        self.value = value # No class, just value. 
        self.declaration = declaration # declaration or None.

# Initialize known_types. 
for t in known_basics.keys():
    known_types[t] = RPCType()


#
# Section: Functions for code generation
#

def gen_pack_code(ip, id, typedecl):
    base_type = known_types[typedecl.base_type]
    if base_type.composite:
        if typedecl.isarray:
            ip.pr("pack_objarray(self, self.%s)" % id)
        else:
            ip.pr("self.%s.pack()" % id)
    else:
        ip.pr("self.packer.pack_%s(self.%s)" % (typedecl.base_type, id))


def gen_unpack_code(ip, id, typedecl):
    base_type = known_types[typedecl.base_type]
    if base_type.composite:
        if typedecl.isarray:
            ip.pr("self.%s = unpack_objarray(self, %s)" % (id, typedecl.base_type))
        else:
            ip.pr("self.%s = %s(self)" % (id, typedecl.base_type))
            ip.pr("self.%s.unpack()" % id)
    else:
        ip.pr("self.%s = self.unpacker.unpack_%s()" % (id, typedecl.base_type))


def gen_packers(id, typeobj):
    base_type = known_types[typeobj.base_type]
    
    # Packers
    ip = IndentPrinter(packer_out)
    ip.change(4)
    if (not base_type.composite) and (not typeobj.isarray):
        # Simple alias
        ip.pr("pack_%s = pack_%s\n" % (id, typeobj.base_type))
    else:
        ip.pr("def pack_%s(self, data):" % id)
        ip.change(4)
        if base_type.composite:
            # Handled by class
            ip.pr("pack_objarray(self, data)")
        else:
            # Array
            if typeobj.base_type == "string":
                ip.pr("self.pack_string(data)")
            elif typeobj.base_type == "opaque":
                if typeobj.fixarray:
                    # Fixed length opaque data
                    ip.pr("self.pack_fopaque(%s, data)" % typeobj.arraylen)
                else:
                    # Variable length opaque data
                    ip.pr("self.pack_opaque(data)")
            else:
                # Some other kind of array. 
                ip.pr("self.pack_array(data, self.pack_%s)" % typeobj.base_type)
        ip.pr("")


    # Unpackers
    ip = IndentPrinter(unpacker_out)
    ip.change(4)
    if (not base_type.composite) and (not typeobj.isarray):
        # Simple alias
        ip.pr("unpack_%s = unpack_%s\n" % (id, typeobj.base_type))
    else:
        ip.pr("def unpack_%s(self):" % id)
        ip.change(4)
        if base_type.composite:
            # Handled by class
            ip.pr("return self.unpack_objarray(self, %s)" % typeobj.base_type)
        else:
            # Array
            if typeobj.base_type == "string":
                ip.pr("return self.unpack_string()")
            elif typeobj.base_type == "opaque":
                if typeobj.fixarray:
                    # Fixed length opaque data
                    ip.pr("return self.unpack_fopaque(%s)" % typeobj.arraylen)
                else:
                    # Variable length opaque data
                    ip.pr("return self.unpack_opaque()")
            else:
                # Some other kind of array. 
                ip.pr("return self.unpack_array(self.unpack_%s)" % typeobj.base_type)
        ip.pr("")
    

def gen_switch_code(ip, union_body, packer, assertions=0):
    # Shortcuts
    switch_var_declaration = union_body.declaration
    switch_var_id = switch_var_declaration[0]
    switch_var_type = switch_var_declaration[1]
    switch_body = union_body.switch_body
    # RPCcase_declaration
    first_case_declaration = switch_body.first_declaration
    # List of RPCcase_declaration:s
    case_list = switch_body.case_list
    # RPCcase_declaration
    default_declaration = switch_body.default_declaration
        
    # Unpack switch value
    (switch_id, typedecl) = switch_var_declaration
    # Assert switch value
    if assertions:
        check_not_reserved(switch_id)
        ip.pr("assert_not_none(self, self.%s)" % switch_id)
    packer(ip, switch_id, typedecl)

    # 1. case_declaration + case_list
    ip.change(4)
    last_empty = 0
    virgin = 1
    for case_declaration in [first_case_declaration] + case_list:
        value = case_declaration.value
        declaration = case_declaration.declaration

        check_not_reserved(switch_id, value)
        if virgin:
            ip.change(-4)
            ip.prcomma("if self.%s == %s" % (switch_id, value))
            virgin = 0
        elif not last_empty:
            ip.change(-4)
            ip.prcomma("elif self.%s == %s" % (switch_id, value))
        else:
            # Last turn had empty declaration. 
            ip.cont(" or self.%s == %s" % (switch_id, value))
            
        if declaration:
            ip.change(4)
            ip.cont(":\n")
            if declaration[0] != "void":
                # check_not_reserved(declaration[0]) is done in packer()
                if assertions: ip.pr("assert_not_none(self, self.%s)" % declaration[0])
                packer(ip, declaration[0], declaration[1])
                ip.pr("self.arm = self.%s" % declaration[0])
            else:
                ip.pr("pass")
            last_empty = 0
        else:
            last_empty = 1
        
    # 2. default_declaration
    ip.change(-4)
    ip.pr("else:")
    ip.change(4)
    if default_declaration:
        declaration = default_declaration.declaration
        if declaration[0] != "void":
            packer(ip, declaration[0], declaration[1])
            ip.pr("self.arm = self.%s" % declaration[0])
        else:
            ip.pr("pass")
    else:
        ip.pr("raise BadDiscriminant(self.%s)" % switch_id)

    ip.pr("\n")
    ip.change(-4)

#
# Section: Parsing
#

# specification 
def p_specification(t):
    '''specification : definition_list'''


# definition
def p_definition_list(t):
    '''definition_list : definition_list definition
                       | empty'''

def p_definition(t):
    '''definition : type_def
                  | constant_def
                  | program_def'''

# type-def
def p_type_def_1(t):
    '''type_def : ENUM ID enum_body SEMI'''
    # Add to known_types; enums are simple
    id = t[2]
    obj = RPCType("enum")
    known_types[id] = obj

    # Write packers
    ip = IndentPrinter(packer_out)
    ip.change(4)
    ip.pr("pack_%s = pack_enum\n" % id)

    # Write unpackers
    ip = IndentPrinter(unpacker_out)
    ip.change(4)
    ip.pr("unpack_%s = unpack_enum\n" % id)
    
    # Returns nothing.


def p_type_def_2(t):
    '''type_def : TYPEDEF declaration SEMI'''

    (id, typeobj) = t[2]
    known_types[id] = typeobj

    print "Creating packers for typedef", id
    gen_packers(id, typeobj)
    # Returns nothing. 

def p_type_def_3(t):
    '''type_def : STRUCT ID struct_body SEMI'''

    print "Creating class for struct", t[2]
    
    # Add to known_types. 
    classname = t[2]
    obj = RPCType(composite=1)
    known_types[classname] = obj

    # Generate class code
    ip = IndentPrinter(types_out)
    struct_body = t[3]

    # class line
    check_not_reserved(classname)
    ip.pr("class %s:" % classname)

    # XDR defintion as comment
    ip.change(4)
    ip.pr("# XDR definition:")
    ip.pr("# struct %s {" % classname)
    for (id, typedecl) in struct_body:
        ip.pr("#     %s %s%s;" % (typedecl.base_type, id, typedecl.array_string()))
    ip.pr("# };")

    # constructor line
    ip.prcomma("def __init__(self, ncl")
    for (id, typedecl) in struct_body:
        check_not_reserved(id)
        ip.cont(", %s=None" % id)
    ip.cont("):\n")

    # constructor body
    ip.change(4)
    ip.pr("init_type_class(self, ncl)")
    for (id, typedecl) in struct_body:
        # check_not_reserved(id) is already done. 
        ip.pr("self.%s = %s" % (id, id))
    ip.cont("\n")

    # __repr__ method
    ip.change(-4)
    ip.pr("def __repr__(self):")
    ip.change(4)
    ip.pr('return "<%s>"' % classname)
    ip.cont("\n")

    # pack method
    ip.change(-4)
    ip.pr("def pack(self, dummy=None):")
    ip.change(4)
    # assert_not_none
    ip.prcomma("assert_not_none(self")
    for (id, typedecl) in struct_body:
        # check_not_reserved(id) is already done. 
        ip.cont(", self.%s" % id)
    ip.cont(")\n")

    for (id, typedecl) in struct_body:
        gen_pack_code(ip, id, typedecl)
    ip.cont("\n")

    # unpack method
    ip.change(-4)
    ip.pr("def unpack(self):")
    ip.change(4)
    for (id, typedecl) in struct_body:
        gen_unpack_code(ip, id, typedecl)
    ip.cont("\n")
    
    # Returns nothing. 
    
def p_type_def_4(t):
    '''type_def : UNION ID union_body SEMI'''

    print "Creating class for union", t[2]
    
    # Add to known_types. 
    classname = t[2]
    obj = RPCType(composite=1)
    known_types[classname] = obj

    # Shortcuts
    union_body = t[3]
    switch_var_declaration = union_body.declaration
    switch_body = union_body.switch_body
    # RPCcase_declaration
    first_case_declaration = switch_body.first_declaration
    # List of RPCcase_declaration:s
    case_list = switch_body.case_list
    # RPCcase_declaration
    default_declaration = switch_body.default_declaration

    # Generate class code
    ip = IndentPrinter(types_out)
    struct_body = t[3]

    # class line
    check_not_reserved(classname)
    ip.pr("class %s:" % classname)

    # XDR defintion as comment
    ip.change(4)
    ip.pr("# XDR definition:")
    ip.pr("# union %s switch (%s %s) {" % (classname,
                                           switch_var_declaration[1].base_type,
                                           switch_var_declaration[0]))

    full_case_list = [first_case_declaration]
    full_case_list += case_list
    if default_declaration:
        full_case_list.append(default_declaration)

    all_decl = [switch_var_declaration]

    for case_decl in full_case_list:
        declaration = case_decl.declaration
        value = case_decl.value

        if value:
            ip.pr("#     case %s:" % value)

            if not declaration:
                continue

            base_type = declaration[1].base_type
            if not base_type:
                base_type = ""
            
            ip.prcomma("#         %s" % base_type)
            ip.cont("    %s%s;" % (declaration[0], declaration[1].array_string()))
            ip.cont("\n")
        else:
            # value was None, this is default declaration.
            ip.pr("#     default:")
            ip.pr("#         %s%s;" % ((declaration[0], declaration[1].array_string())))

        # Keep track of all declarations. 
        if declaration[0] != "void":
            all_decl.append(declaration)
            
    ip.pr("# };")
    

    # constructor line
    ip.prcomma("def __init__(self, ncl")
    for (id, typedecl) in all_decl:
        check_not_reserved(id)
        ip.cont(", %s=None" % id)
    ip.cont("):\n")

    # constructor body
    ip.change(4)
    ip.pr("init_type_class(self, ncl)")
    for (id, typedecl) in all_decl:
        # check_not_reserved(id) already done. 
        ip.pr("self.%s = %s" % (id, id))
    ip.pr("# Shortcut to current arm")
    ip.pr("self.arm = None")
    ip.cont("\n")

    # __repr__ method
    ip.change(-4)
    ip.pr("def __repr__(self):")
    ip.change(4)
    # Ouch! :)
    ip.pr('return "<%s: discriminant:%%d>" %% self.%s' % (classname, switch_var_declaration[0]))
    ip.cont("\n")

    # pack method
    ip.change(-4)
    ip.pr("def pack(self, dummy=None):")
    ip.change(4)    
    gen_switch_code(ip, union_body, gen_pack_code, assertions=1)

    # unpack method
    ip.change(-4)
    ip.pr("def unpack(self):")
    ip.change(4)
    gen_switch_code(ip, union_body, gen_unpack_code)
                    
    # Returns nothing. 


# constant-def
def p_constant_def(t):
    'constant_def : CONST ID EQUALS NUMBER SEMI'
    # Print VAR = value
    check_not_reserved(t[2], t[3], t[4])
    print >> const_out, t[2], t[3], t[4]


# union-body
def p_union_body(t):
    '''union_body : SWITCH LPAREN declaration RPAREN LBRACE switch_body RBRACE'''
    t[0] = RPCunion_body(declaration=t[3], switch_body=t[6])


def p_switch_body(t):
    '''switch_body : case_declaration case_list default_declaration'''
    t[0] = RPCswitch_body(first_declaration=t[1], case_list=t[2],
                          default_declaration=t[3])
    
# The reason for this strange code is that we need to handle constructions like:
#
# case NF4BLK:
# case NF4CHR:
#     specdata4      devdata;
#
# As far as I understand, this is not valid according to RFC1832, but since
# many people seems to use it...
def p_case_declaration(t):
    '''case_declaration : case_value_colon decl_semi'''
    t[0] = RPCcase_declaration(value=t[1], declaration=t[2])

def p_case_value_colon(t):
    '''case_value_colon : CASE value COLON'''
    # Just return value
    t[0] = t[2]

def p_decl_semi(t):
    '''decl_semi : declaration SEMI
                 | empty'''
    # Return declaration or None
    t[0] = t[1]

def p_case_list_1(t):
    '''case_list : case_list case_declaration'''
    if t[1] != None:
        t[1].append(t[2])
        t[0] = t[1]

def p_case_list_2(t):
    '''case_list : empty'''
    # Return []
    t[0] = []

def p_default_declaration_1(t):
    '''default_declaration : DEFAULT COLON decl_semi'''
    t[0] = RPCcase_declaration(value=t[0], declaration=t[3])

def p_default_declaration_2(t):
    '''default_declaration : empty'''
    t[0] = None


# union-type-spec
def p_union_type_spec(t):
    '''union_type_spec : UNION union_body'''
    t[0] = t[2]


# struct-body
def p_struct_body(t):
    '''struct_body : LBRACE struct_declaration struct_declaration_list RBRACE'''
    # Append struct_declaration on struct_declaration_list (which may be []).
    t[0] = [t[2]] + t[3]

def p_struct_declaration(t):
    '''struct_declaration : declaration SEMI'''
    # return declaration
    t[0] = t[1]

def p_struct_declaration_list_1(t):
    '''struct_declaration_list : struct_declaration_list struct_declaration'''
    if t[1] != None:
            t[1].append(t[2])
            t[0] = t[1]

def p_struct_declaration_list_2(t):
    '''struct_declaration_list : empty'''
    # Return []
    t[0] = []

# struct-type-spec
def p_struct_type_spec(t):
    '''struct_type_spec : STRUCT struct_body'''
    # return struct_body
    t[0] = t[2]


# enum-body
def p_enum_body(t):
    '''enum_body : LBRACE enum_body_contents RBRACE'''

def p_enum_body_contents(t):
    '''enum_body_contents : enum_constant enum_constant_list'''

def p_enum_constant(t):
    '''enum_constant : ID EQUALS NUMBER'''
    # Print VAR = value
    check_not_reserved(t[1], t[2], t[3])
    print >> const_out, t[1], t[2], t[3]

def p_enum_constant_list(t):
    '''enum_constant_list : enum_constant_list COMMA enum_constant
                          | empty'''


# enum-type-spec
def p_enum_type_spec(t):
    '''enum_type_spec : ENUM enum_body'''

def p_type_specifier_1(t):
    '''type_specifier : unsigned_specifier INT
                      | unsigned_specifier HYPER'''
    # Two symbols
    if t[1] == None:
        # No "unsigned" specified
        # kind is "int" or "hyper"
        t[0] = t[2]
        return
    elif t[1] == "unsigned":
        # "unsigned" specified
        # kind is unsigned_int or unsigned_hyper
        t[0] = "unsigned_" + t[2]
        return
    else:
        raise "invalid keyword prepending int or hyper"

def p_type_specifier_2(t):
    '''type_specifier : FLOAT
                      | DOUBLE
                      | QUADRUPLE
                      | BOOL
                      | enum_type_spec
                      | struct_type_spec
                      | union_type_spec
                      | ID
                      | UNSIGNED'''
    # One symbol
    t[0] = t[1]

def p_unsigned_specifier(t):
    '''unsigned_specifier : UNSIGNED
                          | empty'''
    # Returns "unsigned" or None.
    t[0] = t[1]


# value
def p_value(t):
    '''value : NUMBER
             | ID'''
    t[0] = t[1]

def p_optional_value(t):
    '''optional_value : value
                      | empty'''
    # return value or None.
    t[0] = t[1]


# declaration
def p_declaration_1(t):
    '''declaration : type_specifier ID'''
    obj = RPCType(t[1])
    # Return tupel of (id, RPCType)
    t[0] = (t[2], obj)

def p_declaration_2(t):
    '''declaration : type_specifier ID LBRACKET value RBRACKET
                   | type_specifier ID LT optional_value GT
                   | OPAQUE ID LBRACKET value RBRACKET
                   | OPAQUE ID LT optional_value GT
                   | STRING ID LT optional_value GT'''
    vararray = None
    fixarray = None
    if t[3] == "[": fixarray = 1
    if t[3] == "<": vararray = 1

    base_type = t[1]
    id = t[2]
    arraylen = t[4]
    obj = RPCType(base_type, fixarray=fixarray, vararray=vararray, arraylen=arraylen, isarray=1)
    t[0] = (id, obj)
               

def p_declaration_3(t):
    '''declaration : type_specifier STAR ID'''
    # Short-cut: We interpret "type-name *identifier"
    # as "type-name identifier<1>".
    obj = RPCType(t[1], vararray=1, arraylen=1, isarray=1)
    id = t[3]
    t[0] = (id, obj)
        

def p_declaration_4(t):
    '''declaration : VOID'''
    obj = RPCType(void=1)
    t[0] = ("void", obj)
 
#
# RPC specific
#
# program-def
def p_program_def(t):
    '''program_def : PROGRAM ID LBRACE version_def version_def_list RBRACE EQUALS NUMBER SEMI'''


# version-def
def p_version_def(t):
    '''version_def : VERSION ID LBRACE procedure_def procedure_def_list RBRACE EQUALS NUMBER SEMI'''

def p_version_def_list(t):
    '''version_def_list : version_def_list version_def
                        | empty'''


# procedure-def
def p_procedure_def(t):
    '''procedure_def : rpc_type_specifier ID LPAREN rpc_type_specifier type_specifier_list RPAREN EQUALS NUMBER SEMI'''

def p_procedure_def_list(t):
    '''procedure_def_list : procedure_def_list procedure_def 
                          | empty'''

def p_type_specifier_list(t):
    '''type_specifier_list : type_specifier_list COMMA rpc_type_specifier
                           | empty'''

def p_rpc_type_specifier(t):
    '''rpc_type_specifier : type_specifier
                          | VOID''' # This is strange and not mentioned in RFC1831/1832. Why?
    
# special 
def p_empty(t):
    'empty :'

def p_error(t):
    print "Syntax error at '%s' (lineno %d)" % (t.value, t.lineno)


#
# Section: main
#
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print "Usage: %s <filename>" % sys.argv[0]
        sys.exit(1)

    infile = sys.argv[1]
    name_base = infile[:infile.rfind(".")]
    constants_file = name_base + "constants.py"
    types_file = name_base + "types.py"
    packer_file = name_base + "packer.py"

    print "Input file is", infile
    print "Writing constants to", constants_file
    print "Writing type classes to", types_file
    print "Writing packer classes to", packer_file

    const_out = open(constants_file, "w")
    types_out = open(types_file, "w")
    packer_file_out = open(packer_file, "w")
    # Write beginning of types file. 
    types_out.write(typesheader)

    packer_out = MemFile()
    packer_out.write("class NFS4Packer(rpc.Packer):\n")
    unpacker_out = MemFile()
    unpacker_out.write("class NFS4Unpacker(rpc.Unpacker):\n")

    # Write beginning of packer file.
    packer_file_out.write(packerheader)
    ip = IndentPrinter(packer_out)
    ip.change(4)
    for t in known_basics.keys():
        packer = known_basics[t]
        ip.pr("pack_%s = rpc.Packer.%s\n" % (t, packer))

    ip = IndentPrinter(unpacker_out)
    ip.change(4)
    for t in known_basics.keys():
        packer = known_basics[t]
        ip.pr("unpack_%s = rpc.Unpacker.%s\n" % (t, "un" + packer))

    import yacc
    yacc.yacc()

    f = open(infile)
    data = f.read()
    f.close()

    yacc.parse(data, debug=0)

    # Write out packer data. 
    packer_file_out.write(packer_out.get_data())
    packer_file_out.write(unpacker_out.get_data())

    const_out.close()
    types_out.close()
    packer_file_out.close()
