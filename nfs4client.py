#!/usr/bin/env python2

# nfs4client.py - NFS4 client. 
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

# TODO:
# completion: should not complete commands as arguments.
# Handle errors such as NFS4ERR_RESOURCE and NFS4ERR_DELAY. 

from nfs4constants import *
from nfs4types import *
import nfs4lib
import cmd
import sys
import getopt
import re
import os
import time

SYNTAX = """\
Syntax:
nfs4client host[:[port]]<directory> [-u|-t] [-d debuglevel]

-u --udp (default)
-t --tcp

-d --debuglevel debuglevel
"""

VERSION = "0.0"
BUFSIZE = 4096

# Load readline & completer
try:
    import readline
    import pynfs_completer
except ImportError:
    print "Module readline not available. Tab-completion disabled."
    class Completer:
        def __init__(self):
            self.pythonmode = 0
    
else:
    # Readline is available
    import __builtin__
    import __main__
    class Completer(pynfs_completer.Completer):
        def __init__(self):
            self.pythonmode = 0
            readline.set_completer(self.complete)
            pynfs_completer.set_history_file(".nfs4client")
        
        commands = [
            "help", "cd", "rm", "dir", "ls", "exit", "quit", "get",
            "put", "mkdir", "md", "rmdir", "rd", "cat", "page",
            "debug", "ping", "version", "pythonmode", "shell", "access",
            "create", "remove"]

        def complete(self, text, state):
            """Return the next possible completion for 'text'.

            This is called successively with state == 0, 1, 2, ... until it
            returns None.  The completion should begin with 'text'.

            """
            if state == 0:
                if "." in text and self.pythonmode:
                    self.matches = self.attr_matches(text)
                else:
                    self.matches = self.global_matches(text)
            try:
                return self.matches[state]
            except IndexError:
                return None

            
        def global_matches(self, text):
            """Compute matches when text is a simple name.

            Return a list of all keywords, built-in functions and names
            currently defines in __main__ that match.

            """
            import keyword
            matches = []
            n = len(text)

            searchlist = [Completer.commands]
            if self.pythonmode:
                searchlist.append(keyword.kwlist)
                searchlist.append(__builtin__.__dict__.keys())
                searchlist.append(__main__.__dict__.keys())

            for list in searchlist:
                for word in list:
                    if word[:n] == text and word != "__builtins__":
                        matches.append(word)

            return matches


class ClientApp(cmd.Cmd):
    def __init__(self, transport, host, port, directory, pythonmode):
        self.transport = transport
        self.host = host
        self.port = port
        self.directory = directory
        self.ncl = None

        self.completer = Completer()
        self.completer.pythonmode = pythonmode

        self.baseprompt = "nfs4: %s>"

        # FIXME
        #self.intro = ""
        #self.doc_header = ""
        #self.misc_header
        #self.undoc_header

        self._connect()
        self._set_prompt()


    def _connect(self):
        if transport == "tcp":
            self.ncl = nfs4lib.TCPNFS4Client(self.host, self.port)
        elif transport == "udp":
            self.ncl = nfs4lib.UDPNFS4Client(self.host, self.port)
        else:
            raise RuntimeError, "Invalid protocol"
        self.ncl.init_connection()

    def _set_prompt(self):
        self.prompt = self.baseprompt % self.ncl.cwd
        

    #
    # Commands
    #
    def do_EOF(self, line):
        print
        sys.exit(0)
    
    def do_cd(self, line):
        if line == "..":
            self.ncl.cwd = self.ncl.cwd[:self.ncl.cwd.rindex("/")]
            if not self.ncl.cwd:
                self.ncl.cwd = "/"
        else:
            candidate_cwd = os.path.join(self.ncl.cwd, line)
            pathcomps = nfs4lib.unixpath2comps(candidate_cwd)
            operations = [self.ncl.putrootfh_op()]
            if pathcomps:
                lookupop = self.ncl.lookup_op(pathcomps)
                operations.append(lookupop)

            res = self.ncl.compound(operations)
            try:
                nfs4lib.check_result(res)
            except nfs4lib.BadCompoundRes, r:
                print "Cannot change directory to %s: %s" % (line, r)
                return

            self.ncl.cwd = candidate_cwd

        self._set_prompt()

    def do_rm(self, line):
        # FIXME
        print "not implemented"

    def do_dir(self, line):
        pathcomps = nfs4lib.unixpath2comps(self.ncl.cwd)

        putrootfhop = self.ncl.putrootfh_op()
        operations = [putrootfhop]
        
        if pathcomps:
            lookupop = self.ncl.lookup_op(pathcomps)
            operations.append(lookupop)

        getfhop = self.ncl.getfh_op()
        operations.append(getfhop)

        res = self.ncl.compound(operations)
        try:
            nfs4lib.check_result(res)
        except nfs4lib.BadCompoundRes, r:
            print "Cannot list directory:", r
            return
            
        getfhresult = res.resarray[-1].arm
        fh = getfhresult.arm.object
        
        entries = self.ncl.do_readdir(fh)
        for entry in entries:
            print entry.name

    do_ls = do_dir

    do_exit = do_EOF

    do_quit = do_EOF

    def do_get(self, line):
        filenames = line.split()

        if not filenames:
            print "get <filename>..."
            return
        
        for file in filenames:
            basename = os.path.basename(file)
            remote = nfs4lib.NFS4OpenFile(self.ncl)
            try:
                remote.open(file)
                local = open(basename, "w")
                while 1:
                    data = remote.read(BUFSIZE)
                    if not data:
                        break
                    
                    local.write(data)
                
                remote.close()
                local.close()
            except nfs4lib.BadCompoundRes, r:
                print "Error fetching file:", r
        print

    def do_access(self, line):
        if not line:
            print "access <filename>"
            return

        allrights = ACCESS4_DELETE + ACCESS4_EXECUTE + ACCESS4_EXTEND + ACCESS4_LOOKUP \
                    + ACCESS4_MODIFY + ACCESS4_READ
        
        pathcomps = self.ncl.get_pathname(line)

        # PUTROOT
        operations = [self.ncl.putrootfh_op()]
        if pathcomps:
            # LOOKUP
            operations.append(self.ncl.lookup_op(pathcomps))

        # ACCESS
        operations.append(self.ncl.access_op(allrights))
        res = self.ncl.compound(operations)
        try:
            nfs4lib.check_result(res)
        except nfs4lib.BadCompoundRes, r:
            print "access failed:", r
            return

        access = res.resarray[-1].arm.arm.access

        def is_allowed(access, bit):
            if access & bit:
                return "allowed"
            else:
                return "not allowed"

        print "ACCESS4_READ is", is_allowed(access, ACCESS4_READ)
        print "ACCESS4_LOOKUP is", is_allowed(access, ACCESS4_LOOKUP)
        print "ACCESS4_MODIFY is", is_allowed(access, ACCESS4_MODIFY)
        print "ACCESS4_EXTEND is", is_allowed(access, ACCESS4_EXTEND)
        print "ACCESS4_DELETE is", is_allowed(access, ACCESS4_DELETE)
        print "ACCESS4_EXECUTE is", is_allowed(access, ACCESS4_EXECUTE)

    def do_create(self, line):
        # FIXME: Should be able to create objects in other dirs than cwd.
        args = line.split()
        if len(args) < 2:
            print "create <type> <name> <arguments>"
            return

        (type, objname) = line.split(None, 3)[:2]
        if type == "link":
            if len(args) < 3:
                print "create link <name> <target>"
                return
            else:
                linkdata = args[2]
            objtype = createtype4(self.ncl, type=NF4LNK, linkdata=linkdata)
        elif type == "block":
            if len(args) < 4:
                print "create block <name> major minor"
                return
            major = int(args[2])
            minor = int(args[3])
            devdata = specdata4(self.ncl, major, minor)
            objtype = createtype4(self.ncl, type=NF4BLK, devdata=devdata)
        elif type == "char":
            if len(args) < 4:
                print "create char <name> major minor"
                return
            major = int(args[2])
            minor = int(args[3])
            devdata = specdata4(self.ncl, major, minor)
            objtype = createtype4(self.ncl, type=NF4CHR, devdata=devdata)
        elif type == "socket":
            objtype = createtype4(self.ncl, type=NF4SOCK)
        elif type == "fifo":
            objtype = createtype4(self.ncl, type=NF4FIFO)
        elif type == "dir":
            objtype = createtype4(self.ncl, type=NF4DIR)
        else:
            print "unknown type"
            return

        # PUTROOT
        operations = [self.ncl.putrootfh_op()]

        # LOOKUP
        pathcomps = nfs4lib.unixpath2comps(self.ncl.cwd)
        if pathcomps:
            operations.append(self.ncl.lookup_op(pathcomps))

        # CREATE
        createop = self.ncl.create_op(objname, objtype)
        operations.append(createop)

        try:
            res = self.ncl.compound(operations)
            nfs4lib.check_result(res)
        except nfs4lib.BadCompoundRes, r:
            print "create failed:", r
            return

    def do_put(self, line):
        # FIXME: Not tested. 
        filenames = line.split()

        if not filenames:
            print "put <filename>..."
            return
        
        for file in filenames:
            basename = os.path.basename(file)
            remote = nfs4lib.NFS4OpenFile(self.ncl)
            try:
                local = open(file)
                remote.open(basename, "w")
                
                while 1:
                    data = local.read(BUFSIZE)
                    if not data:
                        break
                    
                    remote.write(data)
                
                remote.close()
                local.close()
            except nfs4lib.BadCompoundRes, r:
                print "Error fetching file:", r
        print

    def do_mkdir(self, line):
        # FIXME
        print "not implemented"

    do_md = do_mkdir

    def do_rmdir(self, line):
        # FIXME
        print "not implemented"

    do_rd = do_rmdir

    def do_cat(self, line):
        filenames = line.split()

        if not filenames:
            print "cat <filename>..."
            return
        
        for file in filenames:
            f = nfs4lib.NFS4OpenFile(self.ncl)
            try:
                f.open(file)
                print f.read(),
                f.close()
            except nfs4lib.BadCompoundRes, r:
                print "Error fetching file:", r
        print
        
    do_page = do_cat
    
    def do_remove(self, line):
        # FIXME: Should be able to remove objects in other dirs than cwd.
        args = line.split()
        if len(args) != 1:
            print "remove <name>"
            return

        objname = args[0]

        # PUTROOT
        operations = [self.ncl.putrootfh_op()]

        # LOOKUP
        pathcomps = nfs4lib.unixpath2comps(self.ncl.cwd)
        if pathcomps:
            operations.append(self.ncl.lookup_op(pathcomps))

        # REMOVE
        removeop = self.ncl.remove_op(objname)
        operations.append(removeop)

        try:
            res = self.ncl.compound(operations)
            nfs4lib.check_result(res)
        except nfs4lib.BadCompoundRes, r:
            print "remove failed:", r
            return


    def do_debug(self, line):
        # FIXME
        print "not implemented"

    def do_ping(self, line):
        print "pinging", self.ncl.host, "via RPC NULL procedure"
        start = time.time()
        self.ncl.null()
        end = time.time()
        print self.ncl.host, "responded in %f seconds" % (end - start)

    def do_version(self, line):
        print "nfs4client.py version", VERSION

    def do_shell(self, line):
        os.system(line)

    def do_pythonmode(self, line):
        self.completer.pythonmode = (not self.completer.pythonmode)
        print "pythonmode is now",
        if self.completer.pythonmode:
            print "on"
        else:
            print "off"

    #
    # Misc. 
    #
    def help_cd(self):
        print "Change current directory"
    
    def help_overview(self):
        print SYNTAX

    def emptyline(self):
        pass

    def default(self, line):
        if line == "xyzzy":
            print "Beware of black rabbits!"
            return
        
        if not self.completer.pythonmode:
            print "Unknown command", line
            return
        
        if line[:1] == '@':
            line = line[1:]

        try:
            code = compile(line + '\n', '<stdin>', 'single')
            exec code in globals()
        except:
            import traceback
            traceback.print_exc()


def usage():
    USAGE = """\
Usage: %s host[:[port]]<directory> [-u|-t] [-d debuglevel] [-c string] 
options:
-h, --help                   display this help and exit
-u, --udp                    use UDP as transport (default)
-t, --tcp                    use TCP as transport
-d level, --debuglevel level set debuglevel
-p, --pythonmode             enable Python interpreter mode
-c, --commandstring string   execute semicolon separated commands
""" % sys.argv[0]

    print >> sys.stderr, USAGE
    sys.exit(2)


# FIXME: Remove if/when Python library supports GNU style scanning. 
def my_getopt(args, shortopts, longopts = []):
    opts = []
    prog_args = []
    if type(longopts) == type(""):
        longopts = [longopts]
    else:
        longopts = list(longopts)

    # Allow options after non-option arguments?
    if shortopts[0] == '+':
        shortopts = shortopts[1:]
        all_options_first = 1
    elif os.environ.has_key("POSIXLY_CORRECT"):
        all_options_first = 1
    else:
        all_options_first = 0

    while args:
        if args[0] == '--':
            prog_args += args[1:]
            break

        if args[0][:2] == '--':
            opts, args = getopt.do_longs(opts, args[0][2:], longopts, args[1:])
        elif args[0][:1] == '-':
            opts, args = getopt.do_shorts(opts, args[0][1:], shortopts, args[1:])
        else:
            if all_options_first:
                prog_args += args
                break
            else:
                prog_args.append(args[0])
                args = args[1:]

    return opts, prog_args


if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()

    # Let getopt parse the arguments
    try:
        opts, args = my_getopt(sys.argv[1:], "hutd:pc:",
                               ["help", "udp", "tcp", "debuglevel=",
                                "pythonmode", "commandstring="])
    except getopt.GetoptError, e:
        print >> sys.stderr, e
        usage()
        sys.exit(2)

    transport = "udp"
    debuglevel = 0
    pythonmode = 0
    commandstring = None

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        if o in ("-u", "--udp"):
            transport = "udp"
        if o in ("-t", "--tcp"):
            transport = "tcp"
        if o in ("-d", "--debuglevel"):
            debuglevel = a
        if o in ("-p", "--pythonmode"):
            pythonmode = 1
        if o in ("-c", "--commandstring"):
            commandstring = a


    # By now, there should only be one argument left.
    if len(args) != 1:
        print >> sys.stderr, "the number of non-option arguments is not one"
        usage()
    else:
        # Parse host/port/directory part. 
        match = re.search(r'^(?P<host>([a-zA-Z][\w\.]*|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}))'
                          r'(?::(?P<port>\d*))?(?P<dir>/[\w/]*)?$', args[0])
        if not match:
            usage()
        host = match.group("host")
        portstring = match.group("port")
        directory = match.group("dir")

        if portstring:
            port = int(portstring)
        else:
            port = nfs4lib.NFS_PORT

        if not directory:
            directory = "/"

    c = ClientApp(transport, host, port, directory, pythonmode)

    commands = []
    if commandstring:
        commands = commandstring.split(";")

    for command in commands:
        c.onecmd(command)
    
    c.cmdloop()

    
# Local variables:
# py-indent-offset: 4
# tab-width: 8
# End:
