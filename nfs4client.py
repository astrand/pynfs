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

from nfs4constants import *
from nfs4types import *
import nfs4lib
import readline
import cmd
import sys
import getopt
import re


class CLI(cmd.Cmd):
    def __init__(self):
        # FIXME: show current directory. 
        self.prompt = "nfs4: >"
        # FIXME
        #self.intro = ""
        #self.doc_header = ""
        #self.misc_header
        #self.undoc_header

    def do_EOF(self, line):
        print
        sys.exit(0)
    
    def do_cd(self, line):
        print "cd is not implemented yet"

    def help_foo(self):
        print "Change current directory"

    def help_overview(self):
        # FIXME
        print "No info yet."

    def do_shell(self, line):
        # FIXME
        print "Not implemented yet. "

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
        dir = match.group("dir")
        print "host is", host
        print "port is", port
        print "dir is", dir

    
##     import sys
##     if len(sys.argv) < 3:
##         print "Usage: %s <protocol> <host>" % sys.argv[0]
##         sys.exit(1)
    
##     proto = sys.argv[1]
##     host = sys.argv[2]
##     if proto == "tcp":
##         ncl = nfs4lib.TCPNFS4Client(host)
##     elif proto == "udp":
##         ncl = nfs4lib.UDPNFS4Client(host)
##     else:
##         raise RuntimeError, "Wrong protocol"

##     # PUTROOT & GETFH
##     putrootfhoperation = nfs_argop4(ncl, argop=OP_PUTROOTFH)
##     getfhoperation = nfs_argop4(ncl, argop=OP_GETFH)
    
##     res =  ncl.compound([putrootfhoperation, getfhoperation])

##     fh = res.resarray[1].opgetfh.resok4.object
##     print "fh is", repr(fh)




