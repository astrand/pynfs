#!/usr/bin/env python2

# nfs4client.py - NFS4 client. 
#
# Copyright (C) 2001  Peter Åstrand <peter@cendio.se>
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

from nfs4constants import *
from nfs4types import *
import nfs4lib
import readline
import cmd
import sys
import getopt
import re

SYNTAX = """\
Syntax:
nfs4client host[:[port]]<directory> [-u|-t] [-d debuglevel]

-u --udp (default)
-t --tcp

-d --debuglevel debuglevel
"""

VERSION = "0.0"

class CLI(cmd.Cmd):
    def __init__(self):
        # FIXME: show current directory. 
        self.prompt = "nfs4: >"
        # FIXME
        #self.intro = ""
        #self.doc_header = ""
        #self.misc_header
        #self.undoc_header
        self.commands = [
            # Commands
            "help", "cd", "rm", "dir", "ls", "exit", "quit", "get",
            "put", "mkdir", "md", "rmdir", "rd", "cat", "page",
            "debug", "ping", "version"]
            
        readline.parse_and_bind("tab: complete")
        readline.set_completer(self.completer)

    def completer(self, text, state):
        if state == 0:
            self.completions = []
            for c in self.commands:
                if c.find(text) != -1:
                    self.completions.append(c)
        try:
            return self.completions[state]
        except IndexError:
            return None


    #
    # Commands
    #
    def do_EOF(self, line):
        print
        sys.exit(0)
    
    def do_cd(self, line):
        # FIXME
        print "not implemented"

    def do_rm(self, line):
        # FIXME
        print "not implemented"

    def do_dir(self, line):
        # FIXME
        print "not implemented"

    do_ls = do_dir

    do_exit = do_EOF

    do_quit = do_EOF

    def do_get(self, line):
        # FIXME
        print "not implemented"

    def do_put(self, line):
        # FIXME
        print "not implemented"

    def do_mkdir(self, line):
        # FIXME
        print "not implemented"

    do_md = do_mkdir

    def do_rmdir(self, line):
        # FIXME
        print "not implemented"

    do_rd = do_rmdir

    def do_cat(self, line):
        # FIXME
        print "not implemented"

    do_page = do_cat

    def do_debug(self, line):
        # FIXME
        print "not implemented"

    def do_ping(self, line):
        # FIXME
        print "not implemented"

    def do_version(self, line):
        print "nfs4client.py version", VERSION

    def do_shell(self, line):
        # FIXME
        print "Not implemented yet. "

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
        print "Unknown command: %s" % line


def usage():
    print "Usage: %s host[:[port]]<directory> [-u|-t] [-d debuglevel]" % sys.argv[0]
    print "options:"
    print "-h, --help                   display this help and exit"
    print "-u, --udp                    use UDP as transport (default)"
    print "-t, --tcp                    use TCP as transport"
    print "-d level, --debuglevel level set debuglevel"
    sys.exit(2)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hutd", ["help", "udp", "tcp", "debuglevel"])
    except getopt.GetoptError:
        print "invalid option"
        usage()
        sys.exit(2)

    transport = "udp"
    debuglevel = 0

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


    # By now, there should only be one argument left.
    if len(args) != 1:
        usage()
    else:
        # Parse host/port/directory part. 
        match = re.search(r'(?P<host>\w*)(?::(?P<port>\d*))?(?P<dir>[\w/]*)', args[0])
        if not match:
            usage()
        host = match.group("host")
        port = match.group("port")
        dire = match.group("dir")
    
    if transport == "tcp":
        ncl = nfs4lib.TCPNFS4Client(host)
    elif transport == "udp":
        ncl = nfs4lib.UDPNFS4Client(host)
    else:
        raise RuntimeError, "Internal error: wrong protocol"

    
    # PUTROOT & GETFH
    putrootfhoperation = ncl.putrootfh()
    getfhoperation = ncl.getfh()
    res =  ncl.compound([putrootfhoperation, getfhoperation])
    fh = res.resarray[1].opgetfh.resok4.object
    print "fh is", repr(fh)


    # SETCLIENTID4
    op = ncl.setclientid()
    res =  ncl.compound([op])

    clientid = res.resarray[0].arm.resok4.clientid
    setclientid_confirm = res.resarray[0].arm.resok4.setclientid_confirm

    print "got clientid", clientid
    print "got setclientid_confirm", setclientid_confirm


    # SETCLIENTID_CONFIRM
    op = ncl.setclientid_confirm(setclientid_confirm)
    res =  ncl.compound([op])


    # OPEN
    op = ncl.open(clientid=clientid, file=["foo"])
    res =  ncl.compound([putrootfhoperation, op, getfhoperation])
    fh = res.resarray[2].arm.arm.object
    

    # READ
    putfhoperation = ncl.putfh(fh)
    
    op = ncl.read(count=50)
    res = ncl.compound([putfhoperation, op])

    print "Fick filinnehållet:", res.resarray[1].arm.arm.data



c = CLI()
c.cmdloop()

