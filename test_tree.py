#!/usr/bin/env python2

# pynfs - Python NFS4 tools
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


import os
import sys
import socket


def main(treeroot):
    if treeroot == "/":
        print "Refusing to use / as treeroot"
        sys.exit(1)
        
    print "Changing current directory to", treeroot
    os.chdir(treeroot)
    # Sanity check
    if os.getcwd() == "/":
        print "Couldn't change to %s, aborting." % treeroot
        sys.exit(1)

    print "Clearing tree"
    os.system("rm -rf *")

    print "Creating /dev"
    os.mkdir("dev")
    os.symlink("fd0", "dev/floppy")
    os.system("mknod dev/fd0 b 2 0")
    os.system("mknod dev/ttyS0 c 4 64")
    s=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind("dev/log")
    os.mkfifo("dev/initctl")

    print "Creating doc"
    os.mkdir("doc")

    print "Creating doc/README"
    f = open("doc/README", "w")
    f.write("Welcome to this NFS4 server.\n")
    f.write("Enjoy.\n")
    f.close()

    print "Creating directory doc/porting"
    os.mkdir("doc/porting")

    print "Creating doc/porting/TODO"
    f = open("doc/porting/TODO", "w")
    f.write("Need to work on DNIX support...\n")
    f.write("Enjoy.\n")
    f.close()

    print "Creating src"
    os.mkdir("src")

    print "Creating src/hello.c"
    f = open("src/hello.c", "w")
    s = """\
#include <stdio.h>
#include <stdlib.h>

int main()
{
    printf("Hello world!\n");
    exit(0);
}
"""
    f.write(s)
    f.close()

    print "Creating tmp"
    os.mkdir("tmp")
    os.chmod("tmp", 0777)

    print "Creating private directory"
    os.mkdir("private")
    os.chmod("private", 0700)
    

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print "Usage: %s <treeroot>" % sys.argv[0]
        print "Creates tree contents for nfs4st testing"
        sys.exit(1)
    
    main(sys.argv[1])
