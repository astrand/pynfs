#!/usr/bin/env python2

# nfs4st.py - NFS4 server tester
#
# Written by Peter �strand <peter@cendio.se>
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
# Extend unittest with warnings. 


import unittest
import time
import sys

from nfs4constants import *
from nfs4types import *
import nfs4lib

# Global variables
host = None
port = None
transport = "udp"


class NFSTestCase(unittest.TestCase):
    def connect(self):
        if transport == "tcp":
            self.ncl = nfs4lib.TCPNFS4Client(host, port)
        elif transport == "udp":
            self.ncl = nfs4lib.UDPNFS4Client(host, port)
        else:
            raise RuntimeError, "Invalid protocol"

        self.ncl.init_connection()
    
    def failIfRaises(self, excClass, callableObj, *args, **kwargs):
        try:
            apply(callableObj, args, kwargs)
        except excClass, e:
            self.fail(e)
        else:
            return


class AccessTestCase(NFSTestCase):
    maxval = ACCESS4_DELETE + ACCESS4_EXECUTE + ACCESS4_EXTEND + ACCESS4_LOOKUP \
             + ACCESS4_MODIFY + ACCESS4_READ

    def valid_access_ops(self):
        result = []
        for i in range(AccessTestCase.maxval + 1):
            result.append(self.ncl.access_op(i))
        return result

    def invalid_access_ops(self):
        result = []
        for i in [64, 65, 66, 127, 128, 129]:
            result.append(self.ncl.access_op(i))
        return result
    
    def setUp(self):
        self.connect()
        self.putrootfhop = self.ncl.putrootfh_op()

    def testSanityOnDir(self):
        """All valid combinations of ACCESS arguments on directory"""
        for accessop in self.valid_access_ops():
            res = self.ncl.compound([self.putrootfhop, accessop])
            self.failIfRaises(nfs4lib.NFSException, nfs4lib.check_result, res)
            
            supported = res.resarray[1].arm.arm.supported
            access = res.resarray[1].arm.arm.access

            # Server should not return an access bit if this bit is not in supported. 
            self.failIf(access > supported, "access is %d, but supported is %d" % (access, supported))


    def testSanityOnFile(self):
        """All valid combinations of ACCESS arguments on file"""
        path = nfs4lib.str2pathname("/README")
        lookupop = self.ncl.lookup_op(path)
        for accessop in self.valid_access_ops():
            res = self.ncl.compound([self.putrootfhop, lookupop, accessop])
            self.failIfRaises(nfs4lib.NFSException, nfs4lib.check_result, res)

            supported = res.resarray[2].arm.arm.supported
            access = res.resarray[2].arm.arm.access

            # Server should not return an access bit if this bit is not in supported. 
            self.failIf(access > supported, "access is %d, but supported is %d" % (access, supported))

    def testNoExecOnDir(self):
        """ACCESS4_EXECUTE should never be returned for directory"""
        for accessop in self.valid_access_ops():
            res = self.ncl.compound([self.putrootfhop, accessop])
            self.failIfRaises(nfs4lib.NFSException, nfs4lib.check_result, res)
            
            supported = res.resarray[1].arm.arm.supported
            access = res.resarray[1].arm.arm.access

            self.failIf(access & ACCESS4_EXECUTE,
                        "server returned ACCESS4_EXECUTE for root dir (access=%d)" % access)

    def testInvalids(self):
        """ACCESS should fail on invalid arguments"""
        for accessop in self.invalid_access_ops():
            res = self.ncl.compound([self.putrootfhop, accessop])
            self.failUnlessEqual(res.status, NFS4ERR_INVAL,
                                 "server accepts invalid ACCESS request with NFS4_OK, "
                                 "should be NFS4ERR_INVAL")

    def testWithoutFh(self):
        """ACCESS should fail without (cfh)"""
        accessop = self.ncl.access_op(ACCESS4_READ)
        res = self.ncl.compound([accessop])
        self.failUnlessEqual(res.status, NFS4ERR_NOFILEHANDLE)


class CommitTestCase(NFSTestCase):
    def setUp(self):
        self.connect()
        self.putrootfhop = self.ncl.putrootfh_op()

    def testOnDir(self):
        """COMMIT should fail with NFS4ERR_ISDIR on directories"""
        global res
        commitop = self.ncl.commit_op(0, 0)
        res = self.ncl.compound([self.putrootfhop, commitop])
        self.failUnlessEqual(res.status, NFS4ERR_ISDIR)


    def testOffsets(self):
        """Simple COMMIT on file with offset 0, 1 and 2**64 - 1"""
        path = nfs4lib.str2pathname("/README")
        lookupop = self.ncl.lookup_op(path)

        # offset = 0
        commitop = self.ncl.commit_op(0, 0)
        res = self.ncl.compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4_OK)

        # offset = 1
        commitop = self.ncl.commit_op(1, 0)
        res = self.ncl.compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4_OK)

        # offset = 2**64 - 1
        commitop = self.ncl.commit_op(-1, 0)
        res = self.ncl.compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4_OK)


    def testCounts(self):
        """COMMIT on file with count 0, 1 and 2**64 - 1"""
        path = nfs4lib.str2pathname("/README")
        lookupop = self.ncl.lookup_op(path)
        
        # count = 0
        commitop = self.ncl.commit_op(0, 0)
        res = self.ncl.compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4_OK)

        # count = 1
        commitop = self.ncl.commit_op(0, 1)
        res = self.ncl.compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4_OK)

        # count = 2**64 - 1
        commitop = self.ncl.commit_op(0, -1)
        res = self.ncl.compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4_OK)

        

class TestProgram(unittest.TestProgram):
    USAGE = """\
Usage: %(progName)s host[:port] [options] [test] [...]

Options:
  -u, --udp        use UDP as transport (default)
  -t, --tcp        use TCP as transport
  -h, --help       Show this message
  -q, --quiet      Minimal output

Examples:
  %(progName)s                               - run default set of tests
  %(progName)s MyTestSuite                   - run suite 'MyTestSuite'
  %(progName)s MyTestCase.testSomething      - run MyTestCase.testSomething
  %(progName)s MyTestCase                    - run all 'test*' test methods
                                               in MyTestCase
"""
    def parseArgs(self, argv):
        import getopt
        import re
        global host, port, transport

        self.verbosity = 2

        # Reorder arguments, so we can add options at the end 
        ordered_args = []
        for arg in sys.argv[1:]:
            if arg.startswith("-"):
                ordered_args.insert(0, arg)
            else:
                ordered_args.append(arg)
        
        try:
            options, args = getopt.getopt(ordered_args, 'uthq',
                                          ['help', 'quiet', 'udp', 'tcp'])
        except getopt.error, msg:
            self.usageExit(msg)
            
        for opt, value in options:
            if opt in ("-u", "--udp"):
                transport = "udp"
            if opt in ("-t", "--tcp"):
                transport = "tcp"
            if opt in ('-h','--help'):
                self.usageExit()
            if opt in ('-q','--quiet'):
                self.verbosity = 0

        if len(args) < 1:
            self.usageExit()

        match = re.search(r'^(?P<host>([a-zA-Z][\w\.]*|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}))'
                          r'(?::(?P<port>\d*))?$', args[0])

        if not match:
            self.usageExit()

        host = match.group("host")
        portstring = match.group("port")

        if portstring:
            port = int(portstring)
        else:
            port = nfs4lib.NFS_PORT

        args = args[1:]
                    
        if len(args) == 0 and self.defaultTest is None:
            self.test = self.testLoader.loadTestsFromModule(self.module)
            return
        if len(args) > 0:
            self.testNames = args
        else:
            self.testNames = (self.defaultTest,)

        self.createTests()


main = TestProgram

if __name__ == "__main__":
    main()
