#!/usr/bin/env python2

# nfs4st.py - NFS4 server tester
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
# Extend unittest with warnings.
# Handle errors such as NFS4ERR_RESOURCE and NFS4ERR_DELAY. 

# Note on docstrings: Each class inheriting NFSTestCase is referred to as a
# "test case". Each test* method is a "invocable component", sometimes called
# "component". 


import unittest
import time
import sys

import rpc
from nfs4constants import *
from nfs4types import *
import nfs4lib


# Global variables
host = None
port = None
transport = "udp"





class NFSTestCase(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        unittest.TestCase.__init__(self, methodName)
    
        # Filename constants
        self.linkfile = "/dev/floppy"
        self.blockfile = "/dev/fd0"
        self.charfile = "/dev/ttyS0"
        self.socketfile = "/dev/log"
        self.fifofile = "/dev/initctl"
        self.dirfile = "/doc"
        self.normfile = "/doc/README"
    
    def connect(self):
        if transport == "tcp":
            self.ncl = nfs4lib.TCPNFS4Client(host, port)
        elif transport == "udp":
            self.ncl = nfs4lib.UDPNFS4Client(host, port)
        else:
            raise RuntimeError, "Invalid protocol"

        self.ncl.init_connection()
    
    def failIfRaises(self, excClass, callableObj, *args, **kwargs):
        """Fail if exception of excClass is raised"""
        try:
            return apply(callableObj, args, kwargs)
        except excClass, e:
            self.fail(e)

    def assert_OK(self, res):
        """Assert result from compound call is NFS4_OK"""
        self.assert_status(res, [NFS4_OK])

    def assert_status(self, res, errors):
        """Assert result from compound call is any of the values in errors"""
        if res.status in errors:
            return

        if res.resarray:
            lastop = res.resarray[-1]
            e = nfs4lib.BadCompoundRes(lastop.resop, lastop.arm.status)
            self.fail(e)
        else:
            self.fail(nfs4lib.EmptyCompoundRes())

    def info_message(self, msg):
        print >> sys.stderr, msg + ", ",

    def do_compound(self, *args, **kwargs):
        """Call ncl.compound. Handle all rpc.RPCExceptions as failures."""
        return self.failIfRaises(rpc.RPCException, self.ncl.compound, *args, **kwargs)

    def lookup_all_objects(self):
        """Generate a list of lookup operations with all types of objects"""
        result = []
        for name in [self.linkfile, self.blockfile, self.charfile, self.socketfile,
                     self.fifofile, self.dirfile, self.normfile]:
            path = nfs4lib.str2pathname(name)
            result.append(self.ncl.lookup_op(path))

        return result


class CompoundTestCase(NFSTestCase):
    """Test COMPOUND procedure

    Equivalence partitioning:

    Input Condition: tag
        Valid equivalence classes:
            no tag (0)
            tag (1)
        Invalid equivalence classes:
            -
    Input Condition: minorversion
        Valid equivalence classes:
            supported minorversions(2)
        Invalid equivalence classes:
            unsupported minorversions(3)
    Input Condition: argarray
        Valid equivalence classes:
            valid operations array(4)
        Invalid equivalence classes:
            invalid operations array(5)

    """

    def setUp(self):
        self.connect()
        self.putrootfhop = self.ncl.putrootfh_op()

    #
    # Testcases covering valid equivalence classes.
    #
    def testZeroOps(self):
        """Test COMPOUND without operations

        Covered valid equivalence classes: 0, 2, 4
        """
        res = self.do_compound([])
        self.assert_OK(res)

    def testWithTag(self):
        """Simple COMPOUND with tag

        Covered valid equivalence classes: 1, 2, 4
        """
        res = self.do_compound([self.putrootfhop], tag="nfs4st.py test tag")
        self.assert_OK(res)

    #
    # Testcases covering invalid equivalence classes.
    #
    def testInvalidMinor(self):
        """Test COMPOUND with invalid minor version

        Covered invalid equivalence classes: 3

        Comments: Also verifies that the result array after
        NFS4ERR_MINOR_VERS_MISMATCH is empty. 
        
        """
        res = self.do_compound([self.putrootfhop], minorversion=0xFFFF)
        self.failIf(res.status != NFS4ERR_MINOR_VERS_MISMATCH,
                    "expected NFS4ERR_MINOR_VERS_MISMATCH")
                    
        self.failIf(res.resarray, "expected empty result array after"\
                    "NFS4ERR_MINOR_VERS_MISMATCH")

    def testOperation0_1_2(self):
        """Test COMPOUND with (undefined) operation 0, 1 and 2

        Covered invalid equivalence classes: 5

        Comments: The server should return NFS4ERR_NOTSUPP for the
        undefined operations 0, 1 and 2. Although operation 2 may be
        introduced in later minor versions, the server should always
        return NFS4ERR_NOTSUPP if the minorversion is 0.
        """

        # nfs4types.nfs_argop4 does not allow packing invalid operations. 
        class custom_nfs_argop4:
            def __init__(self, ncl, argop):
                self.ncl = ncl
                self.packer = ncl.packer
                self.unpacker = ncl.unpacker
                self.argop = argop
            
            def pack(self, dummy=None):
                self.packer.pack_nfs_opnum4(self.argop)

        op = custom_nfs_argop4(self.ncl, argop=0)
        res = self.do_compound([op])
        self.assert_status(res, [NFS4ERR_NOTSUPP])

        op = custom_nfs_argop4(self.ncl, argop=1)
        res = self.do_compound([op])
        self.assert_status(res, [NFS4ERR_NOTSUPP])

        op = custom_nfs_argop4(self.ncl, argop=2)
        res = self.do_compound([op])
        self.assert_status(res, [NFS4ERR_NOTSUPP])


class AccessTestCase(NFSTestCase):
    """Test ACCESS operation.

    Note: We do not examine if the "access" result actually corresponds to
    the correct rights. This is hard since the rights for a object can
    change at any time.

    Equivalence partitioning:
    
    Input Condition: current filehandle
        Valid equivalence classes:
            link(1)
            block(2)
            char(3)
            socket(4)
            FIFO(5)
            dir(6)
            file(7)
        Invalid equivalence classes:
            invalid filehandle(8)
    Input Condition: accessreq
        Valid equivalence classes:
            valid accessreq(9)
        Invalid equivalence classes:
            invalid accessreq(10)
    """
            
    
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

    #
    # Testcases covering valid equivalence classes.
    #
    def testAllObjects(self):
        """ACCESS on all type of objects

        Covered valid equivalence classes: 1, 2, 3, 4, 5, 6, 7, 9
        
        """
        for lookupop in self.lookup_all_objects():
            accessop = self.ncl.access_op(ACCESS4_READ)
            res = self.do_compound([self.putrootfhop, lookupop, accessop])
            self.assert_OK(res)
        
    def testDir(self):
        """All valid combinations of ACCESS arguments on directory

        Covered valid equivalence classes: 6, 9

        Comments: The ACCESS operation takes an uint32_t as an
        argument, which is bitwised-or'd with zero or more of all
        ACCESS4* constants. This component tests all valid
        combinations of these constants. It also verifies that the
        server does not respond with a right in "access" but not in
        "supported".
        """
        
        for accessop in self.valid_access_ops():
            res = self.do_compound([self.putrootfhop, accessop])
            self.assert_OK(res)
            
            supported = res.resarray[1].arm.arm.supported
            access = res.resarray[1].arm.arm.access

            # Server should not return an access bit if this bit is not in supported. 
            self.failIf(access > supported, "access is %d, but supported is %d" % (access, supported))

    def testFile(self):
        """All valid combinations of ACCESS arguments on file

        Covered valid equivalence classes: 7, 9

        Comments: See testDir. 
        """
        path = nfs4lib.str2pathname(self.normfile)
        lookupop = self.ncl.lookup_op(path)
        for accessop in self.valid_access_ops():
            res = self.do_compound([self.putrootfhop, lookupop, accessop])
            self.assert_OK(res)

            supported = res.resarray[2].arm.arm.supported
            access = res.resarray[2].arm.arm.access

            # Server should not return an access bit if this bit is not in supported. 
            self.failIf(access > supported, "access is %d, but supported is %d" % (access, supported))

    #
    # Testcases covering invalid equivalence classes.
    #
    def testWithoutFh(self):
        """ACCESS should return NFS4ERR_NOFILEHANDLE if called without filehandle.

        Covered invalid equivalence classes: 8
        
        """
        accessop = self.ncl.access_op(ACCESS4_READ)
        res = self.do_compound([accessop])
        self.failUnlessEqual(res.status, NFS4ERR_NOFILEHANDLE)


    def testInvalids(self):
        """ACCESS should fail on invalid arguments

        Covered invalid equivalence classes: 10

        Comments: ACCESS should return with NFS4ERR_INVAL if called
        with an illegal access request (eg. an integer with bits set
        that does not correspond to any ACCESS4* constant).
        """
        for accessop in self.invalid_access_ops():
            res = self.do_compound([self.putrootfhop, accessop])
            self.failUnlessEqual(res.status, NFS4ERR_INVAL,
                                 "server accepts invalid ACCESS request with NFS4_OK, "
                                 "should be NFS4ERR_INVAL")
    #
    # Misc. tests.
    #
    def testNoExecOnDir(self):
        """ACCESS4_EXECUTE should never be returned for directory

        Covered valid equivalence classes: 6, 9

        Comments: ACCESS4_EXECUTE has no meaning for directories and
        should not be returned in "access" or "supported".
        """
        for accessop in self.valid_access_ops():
            res = self.do_compound([self.putrootfhop, accessop])
            self.assert_OK(res)
            
            supported = res.resarray[1].arm.arm.supported
            access = res.resarray[1].arm.arm.access

            self.failIf(supported & ACCESS4_EXECUTE,
                        "server returned ACCESS4_EXECUTE for root dir (supported=%d)" % supported)

            self.failIf(access & ACCESS4_EXECUTE,
                        "server returned ACCESS4_EXECUTE for root dir (access=%d)" % access)

    

class CommitTestCase(NFSTestCase):
    """Test COMMIT operation.

    Equivalence partitioning:

    Input Condition: currrent filehandle
        Valid equivalence classes:
            file(1)
        Invalid equivalence classes:
            link(2)
            block(3)
            char(4)
            socket(5)
            FIFO(6)
            dir(7)
            invalid filehandle(8)
    Input Condition: offset
        Valid equivalence classes:
            zero(9)
            nonzero(10)
        Invalid equivalence classes:
            -
    Input Condition: count
        Valid equivalence classes:
            zero(11)
            nonzero(12)
        Invalid equivalence classes:
            -
            
    Note: We do not examine the writeverifier in any way. It's hard
    since it can change at any time.
    """

    def setUp(self):
        self.connect()
        self.putrootfhop = self.ncl.putrootfh_op()

    #
    # Testcases covering valid equivalence classes.
    #
    def testOffsets(self):
        """Simple COMMIT on file with offset 0, 1 and 2**64 - 1

        Covered valid equivalence classes: 1, 9, 10, 11

        Comments: This component tests boundary values for the offset
        parameter in the COMMIT operation. All values are
        legal. Tested values are 0, 1 and 2**64 - 1 (selected by BVA)
        """
        path = nfs4lib.str2pathname(self.normfile)
        lookupop = self.ncl.lookup_op(path)

        # offset = 0
        commitop = self.ncl.commit_op(0, 0)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.assert_OK(res)

        # offset = 1
        commitop = self.ncl.commit_op(1, 0)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.assert_OK(res)

        # offset = 2**64 - 1
        commitop = self.ncl.commit_op(-1, 0)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.assert_OK(res)

    def testCounts(self):
        """COMMIT on file with count 0, 1 and 2**64 - 1

        Covered valid equivalence classes: 1, 9, 11, 12

        This component tests boundary values for the count parameter
        in the COMMIT operation. All values are legal. Tested values
        are 0, 1 and 2**64 - 1 (selected by BVA)
        """
        path = nfs4lib.str2pathname(self.normfile)
        lookupop = self.ncl.lookup_op(path)
        
        # count = 0
        commitop = self.ncl.commit_op(0, 0)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.assert_OK(res)

        # count = 1
        commitop = self.ncl.commit_op(0, 1)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.assert_OK(res)

        # count = 2**64 - 1
        commitop = self.ncl.commit_op(0, -1)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.assert_OK(res)


    #
    # Testcases covering invalid equivalence classes
    #
    def testOnLink(self):
        """COMMIT should fail with NFS4ERR_INVAL on Links

        Covered invalid equivalence classes: 2
        """

        path = nfs4lib.str2pathname(self.linkfile)
        lookupop = self.ncl.lookup_op(path)
        commitop = self.ncl.commit_op(0, 0)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4ERR_INVAL)

    def testOnBlock(self):
        """COMMIT should fail with NFS4ERR_INVAL on block device
        
        Covered invalid equivalence classes: 3
        """

        path = nfs4lib.str2pathname(self.blockfile)
        lookupop = self.ncl.lookup_op(path)
        commitop = self.ncl.commit_op(0, 0)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4ERR_INVAL)

    def testOnChar(self):
        """COMMIT should fail with NFS4ERR_INVAL on character device

        Covered invalid equivalence classes: 4
        """

        path = nfs4lib.str2pathname(self.charfile)
        lookupop = self.ncl.lookup_op(path)
        commitop = self.ncl.commit_op(0, 0)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4ERR_INVAL)

    def testOnSocket(self):
        """COMMIT should fail with NFS4ERR_INVAL on socket

        Covered invalid equivalence classes: 5
        """
        
        path = nfs4lib.str2pathname(self.socketfile)
        lookupop = self.ncl.lookup_op(path)
        commitop = self.ncl.commit_op(0, 0)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4ERR_INVAL)

    def testOnFifo(self):
        """COMMIT should fail with NFS4ERR_INVAL on FIFOs

        Covered invalid equivalence classes: 6
        """

        path = nfs4lib.str2pathname(self.fifofile)
        lookupop = self.ncl.lookup_op(path)
        commitop = self.ncl.commit_op(0, 0)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4ERR_INVAL)
        
    def testOnDir(self):
        """COMMIT should fail with NFS4ERR_ISDIR on directories

        Covered invalid equivalence classes: 7
        """

        path = nfs4lib.str2pathname(self.dirfile)
        lookupop = self.ncl.lookup_op(path)
        commitop = self.ncl.commit_op(0, 0)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4ERR_ISDIR)

    def testWithoutFh(self):
        """COMMIT should return NFS4ERR_NOFILEHANDLE if called without filehandle.

        Covered invalid equivalence classes: 8
        
        """
        commitop = self.ncl.commit_op(0, 0)
        res = self.do_compound([commitop])
        self.failUnlessEqual(res.status, NFS4ERR_NOFILEHANDLE)

    #
    # Misc. tests.
    #
    def testOverflow(self):
        """COMMIT on file with offset+count >= 2**64 should fail

        Covered valid equivalence classes: 1, 10, 12

        Comments: If the COMMIT operation is called with an offset
        plus count that is larger than 2**64, the server should return
        NFS4ERR_INVAL
        """
        
        path = nfs4lib.str2pathname(self.normfile)
        lookupop = self.ncl.lookup_op(path)
        
        commitop = self.ncl.commit_op(-1, -1)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4ERR_INVAL,
                             "no NFS4ERR_INVAL on overflow")


class CreateTestCase(NFSTestCase):
    """Test CREATE operation.

    Equivalence partitioning:

    Input Condition: currrent filehandle
        Valid equivalence classes:
            dir(1)
        Invalid equivalence classes:
            not dir(2)
            no filehandle(3)
    Input Condition: name
        Valid equivalence classes:
            legal name(4)
        Invalid equivalence classes:
            zero length(5)
    Input Condition: type
        Valid equivalence classes:
            link(6)
            blockdev(7)
            chardev(8)
            socket(9)
            FIFO(10)
            directory(11)
        Invalid equivalence classes:
            regular file(12)
    """
    
    def setUp(self):
        self.connect()
        self.putrootfhop = self.ncl.putrootfh_op()
        self.obj_dir = "/tmp"
        self.obj_name = "object1"

        pathname = nfs4lib.str2pathname(self.obj_dir)
        self.lookup_dir_op = self.ncl.lookup_op(pathname)

        # Make sure the object to create does not exist.
        # This tests at the same time the REMOVE operation. Not much
        # we can do about it. 
        operations = [self.ncl.putrootfh_op()]
        operations.append(self.lookup_dir_op)
        operations.append(self.ncl.remove_op(self.obj_name))

        res = self.do_compound(operations)
        self.assert_status(res, [NFS4_OK, NFS4ERR_NOENT])


    #
    # Testcases covering valid equivalence classes.
    #
    def testLink(self):
        """CREATE (symbolic) link

        Covered valid equivalence classes: 1, 4, 6
        """

        operations = [self.putrootfhop, self.lookup_dir_op]
        objtype = createtype4(self.ncl, type=NF4LNK, linkdata="/etc/X11")
        createop = self.ncl.create_op(self.obj_name, objtype)
        operations.append(createop)

        res = self.do_compound(operations)
        if res.status == NFS4ERR_BADTYPE:
            self.info_message("links not supported")
        self.assert_status(res, [NFS4_OK, NFS4ERR_BADTYPE])

    def testBlock(self):
        """CREATE a block device

        Covered valid equivalence classes: 1, 4, 7
        """

        operations = [self.putrootfhop, self.lookup_dir_op]
        devdata = specdata4(self.ncl, 1, 2)
        objtype = createtype4(self.ncl, type=NF4BLK, devdata=devdata)
        createop = self.ncl.create_op(self.obj_name, objtype)
        operations.append(createop)

        res = self.do_compound(operations)
        if res.status == NFS4ERR_BADTYPE:
            self.info_message("blocks devices not supported")
        self.assert_status(res, [NFS4_OK, NFS4ERR_BADTYPE])

    def testChar(self):
        """CREATE a character device

        Covered valid equivalence classes: 1, 4, 8
        """

        operations = [self.putrootfhop, self.lookup_dir_op]
        devdata = specdata4(self.ncl, 1, 2)
        objtype = createtype4(self.ncl, type=NF4CHR, devdata=devdata)
        createop = self.ncl.create_op(self.obj_name, objtype)
        operations.append(createop)

        res = self.do_compound(operations)
        if res.status == NFS4ERR_BADTYPE:
            self.info_message("character devices not supported")
        self.assert_status(res, [NFS4_OK, NFS4ERR_BADTYPE])

    def testSocket(self):
        """CREATE a socket

        Covered valid equivalence classes: 1, 4, 9
        """

        operations = [self.putrootfhop, self.lookup_dir_op]
        objtype = createtype4(self.ncl, type=NF4SOCK)
        createop = self.ncl.create_op(self.obj_name, objtype)
        operations.append(createop)

        res = self.do_compound(operations)
        if res.status == NFS4ERR_BADTYPE:
            self.info_message("sockets not supported")
        self.assert_status(res, [NFS4_OK, NFS4ERR_BADTYPE])

    def testFIFO(self):
        """CREATE a FIFO

        Covered valid equivalence classes: 1, 4, 10
        """
        
        operations = [self.putrootfhop, self.lookup_dir_op]
        objtype = createtype4(self.ncl, type=NF4FIFO)
        createop = self.ncl.create_op(self.obj_name, objtype)
        operations.append(createop)

        res = self.do_compound(operations)
        if res.status == NFS4ERR_BADTYPE:
            self.info_message("FIFOs not supported")
        self.assert_status(res, [NFS4_OK, NFS4ERR_BADTYPE])

    def testDir(self):
        """CREATE a directory

        Covered valid equivalence classes: 1, 4, 11
        """

        operations = [self.putrootfhop, self.lookup_dir_op]
        objtype = createtype4(self.ncl, type=NF4DIR)
        createop = self.ncl.create_op(self.obj_name, objtype)
        operations.append(createop)

        res = self.do_compound(operations)
        if res.status == NFS4ERR_BADTYPE:
            self.info_message("directories not supported!")
        self.assert_status(res, [NFS4_OK, NFS4ERR_BADTYPE])

    #
    # Testcases covering invalid equivalence classes.
    #
    def testFhNotDir(self):
        """CREATE should fail with NFS4ERR_NOTDIR if (cfh) is not dir

        Covered invalid equivalence classes: 2
        """
        
        pathname = nfs4lib.str2pathname(self.normfile)
        lookupop = self.ncl.lookup_op(pathname)
        
        operations = [self.putrootfhop, lookupop]
        objtype = createtype4(self.ncl, type=NF4DIR)
        createop = self.ncl.create_op(self.obj_name, objtype)
        operations.append(createop)

        res = self.do_compound(operations)
        self.assert_status(res, [NFS4ERR_NOTDIR])

    def testNoFh(self):
        """CREATE should fail with NFS4ERR_NOFILEHANDLE if no (cfh)

        Covered invalid equivalence classes: 3
        """
        
        objtype = createtype4(self.ncl, type=NF4DIR)
        createop = self.ncl.create_op(self.obj_name, objtype)

        res = self.do_compound([createop])
        self.assert_status(res, [NFS4ERR_NOFILEHANDLE])

    def testZeroLengthName(self):
        """CREATE with zero length name should fail

        Covered invalid equivalence classes: 5
        """
        operations = [self.putrootfhop, self.lookup_dir_op]
        objtype = createtype4(self.ncl, type=NF4DIR)
        createop = self.ncl.create_op("", objtype)
        operations.append(createop)

        res = self.do_compound(operations)
        self.assert_status(res, [NFS4ERR_INVAL])

    def testRegularFile(self):
        """CREATE should fail with NFS4ERR_INVAL for regular files

        Covered invalid equivalence classes: 12
        """
        operations = [self.putrootfhop, self.lookup_dir_op]

        # nfs4types.createtype4 does not allow packing invalid types
        class custom_createtype4(createtype4):
            def pack(self, dummy=None):
                assert_not_none(self, self.type)
                self.packer.pack_nfs_ftype4(self.type)
            
        objtype = custom_createtype4(self.ncl, type=NF4REG)
        createop = self.ncl.create_op(self.obj_name, objtype)
        operations.append(createop)

        res = self.do_compound(operations)
        self.assert_status(res, [NFS4ERR_INVAL])


class GetattrTestCase(NFSTestCase):
    """Test GETATTR operation.

    Equivalence partitioning:

    Input Condition: currrent filehandle
        Valid equivalence classes:
            file(1)
            link(2)
            block(3)
            char(4)
            socket(5)
            FIFO(6)
            dir(7)
        Invalid equivalence classes:
            invalid filehandle(8)
    Input Condition: attrbits
        Valid equivalence classes:
            all requests without FATTR4_*_SET (9)
        Invalid equivalence classes:
            requests with FATTR4_*_SET (10)
    
    """

    def setUp(self):
        self.connect()
        self.putrootfhop = self.ncl.putrootfh_op()

    #
    # Testcases covering valid equivalence classes.
    #
    def testAllObjects(self):
        """GETATTR(FATTR4_SIZE) on all type of objects

        Covered valid equivalence classes: 1, 2, 3, 4, 5, 6, 7, 9
        
        """
        for lookupop in self.lookup_all_objects():
            getattrop = self.ncl.getattr_op([FATTR4_SIZE])
            res = self.do_compound([self.putrootfhop, lookupop, getattrop])
            self.assert_OK(res)

    #
    # Testcases covering invalid equivalence classes.
    #
    def testNoFh(self):
        """GETATTR should fail with NFS4ERR_NOFILEHANDLE if no (cfh)

        Covered invalid equivalence classes: 8
        """
        
        getattrop = self.ncl.getattr_op([FATTR4_SIZE])
        res = self.do_compound([getattrop])
        self.assert_status(res, [NFS4ERR_NOFILEHANDLE])

    def testWriteOnlyAttributes(self):
        """GETATTR(FATTR4_*_SET) should return NFS4ERR_INVAL

        Covered invalid equivalence classes: 10

        Comments: Some attributes are write-only (currently
        FATTR4_TIME_ACCESS_SET and FATTR4_TIME_MODIFY_SET). If GETATTR
        is called with any of these, NFS4ERR_INVAL should be returned.
        """
        path = nfs4lib.str2pathname(self.normfile)
        lookupop = self.ncl.lookup_op(path)

        getattrop = self.ncl.getattr([FATTR4_TIME_ACCESS_SET])
        res = self.do_compound([self.putrootfhop, lookupop, getattrop])
        self.failUnlessEqual(res.status, NFS4ERR_INVAL)

    #
    # Misc. tests.
    #
    def testAllMandatory(self):
        """Assure GETATTR can return all mandatory attributes

        Covered valid equivalence classes: 1, 9

        Comments: A server should be able to return all mandatory
        attributes.
        """

        attrbitnum_dict = nfs4lib.get_attrbitnum_dict()
        all_mandatory_names = [
            "supported_attrs", 
            "type",
            "fh_expire_type",
            "change",
            "size",
            "link_support",
            "symlink_support",
            "named_attr",
            "fsid",
            "unique_handles",
            "lease_time",
            "rdattr_error"]
        all_mandatory = []
        
        for attrname in all_mandatory_names:
            all_mandatory.append(attrbitnum_dict[attrname])
        
        path = nfs4lib.str2pathname(self.normfile)
        lookupop = self.ncl.lookup_op(path)
        getattrop = self.ncl.getattr(all_mandatory)
        
        res = self.do_compound([self.putrootfhop, lookupop, getattrop])
        self.assert_OK(res)
        obj = res.resarray[-1].arm.arm.obj_attributes
        d = nfs4lib.fattr2dict(obj)

        unsupported = []
        keys = d.keys()
        for attrname in all_mandatory_names:
            if not attrname in keys:
                unsupported.append(attrname)

        if unsupported:
            self.fail("mandatory attributes not supported: %s" % str(unsupported))

    def testUnknownAttr(self):
        """GETATTR should not fail on unknown attributes

        Covered valid equivalence classes: 1, 9

        Comments: This test calls GETATTR with request for attribute
        number 1000.  Servers should not fail on unknown attributes.
        """
        path = nfs4lib.str2pathname(self.normfile)
        lookupop = self.ncl.lookup_op(path)

        getattrop = self.ncl.getattr([1000])
        res = self.do_compound([self.putrootfhop, lookupop, getattrop])
        self.assert_OK(res)

    def testEmptyCall(self):
        """GETATTR should accept empty request

        Covered valid equivalence classes: 1, 9

        Comments: GETATTR should accept empty request
        """

        path = nfs4lib.str2pathname(self.normfile)
        lookupop = self.ncl.lookup_op(path)

        getattrop = self.ncl.getattr([])
        res = self.do_compound([self.putrootfhop, lookupop, getattrop])
        self.assert_OK(res)

    def testSupported(self):
        """GETATTR(FATTR4_SUPPORTED_ATTRS) should return all mandatory

        Covered valid equivalence classes: 1, 9
        
        Comments: GETATTR(FATTR4_SUPPORTED_ATTRS) should return at
        least all mandatory attributes
        """

        path = nfs4lib.str2pathname(self.normfile)
        lookupop = self.ncl.lookup_op(path)

        getattrop = self.ncl.getattr([FATTR4_SUPPORTED_ATTRS])
        res = self.do_compound([self.putrootfhop, lookupop, getattrop])
        self.assert_OK(res)

        obj = res.resarray[-1].arm.arm.obj_attributes

        unpacker = nfs4lib.create_dummy_unpacker(obj.attr_vals)
        intlist = unpacker.unpack_fattr4_supported_attrs()
        i = nfs4lib.intlist2long(intlist)

        all_mandatory_bits = 2**(FATTR4_RDATTR_ERROR+1) - 1

        returned_mandatories = i & all_mandatory_bits

        self.failIf(not returned_mandatories == all_mandatory_bits,
                    "not all mandatory attributes returned: %s" % \
                    nfs4lib.int2binstring(returned_mandatories)[-12:])

        sys.stdout.flush()



class QuietTextTestRunner(unittest.TextTestRunner):
    def _makeResult(self):
        ttr = unittest._TextTestResult(self.stream, self.descriptions, self.verbosity)
        ttr.printErrors = lambda: 0
        return ttr
    

class TestProgram(unittest.TestProgram):
    USAGE = """\
Usage: %(progName)s host[:port] [options] [test] [...]

Options:
  -u, --udp        use UDP as transport (default)
  -t, --tcp        use TCP as transport
  -h, --help       Show this message
  -q, --quiet      Minimal output
  -v, --verbose    Verbose output, display tracebacks

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
        self.display_tracebacks = 0

        # Reorder arguments, so we can add options at the end 
        ordered_args = []
        for arg in sys.argv[1:]:
            if arg.startswith("-"):
                ordered_args.insert(0, arg)
            else:
                ordered_args.append(arg)
        
        try:
            options, args = getopt.getopt(ordered_args, 'uthqv',
                                          ['help', 'quiet', 'udp', 'tcp', 'verbose'])
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
            if opt in ('-v','--verbose'):
                self.display_tracebacks = 1

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

    def runTests(self):
        if self.display_tracebacks:
            self.testRunner = unittest.TextTestRunner(verbosity=self.verbosity)
        else:
            self.testRunner = QuietTextTestRunner(verbosity=self.verbosity)
        result = self.testRunner.run(self.test)
        sys.exit(not result.wasSuccessful())


main = TestProgram

if __name__ == "__main__":
    main()
