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
#
# use assert_status instead of failIf. 
#
# Extend unittest with warnings.
#
# Handle errors such as NFS4ERR_RESOURCE and NFS4ERR_DELAY.
#
# More tests on strings not obeying UTF-8.
#
# filehandles are split into eq. classes "valid filehandle" and
# "invalid filehandle". There should probably be a class "no filehandle" as
# well. Currently, "invalid filehandle" are tested by doing operations without
# filehandles. 

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
    
        # Filename constants. Same order as in nfs_ftype4 enum. 
        self.normfile = nfs4lib.unixpath2comps("/doc/README") # NF4REG
        self.dirfile = nfs4lib.unixpath2comps("/doc") # NF4DIR
        self.blockfile = nfs4lib.unixpath2comps("/dev/fd0") # NF4DIR
        self.charfile = nfs4lib.unixpath2comps("/dev/ttyS0") # NF4CHR
        self.linkfile = nfs4lib.unixpath2comps("/dev/floppy") # NF4LNK
        self.socketfile = nfs4lib.unixpath2comps("/dev/log") # NF4SOCK
        self.fifofile = nfs4lib.unixpath2comps("/dev/initctl") # NF4FIFO

        # FIXME: Add sample named attribute.
        self.tmp_dir = nfs4lib.unixpath2comps("/tmp")

        # Some more filenames
        self.hello_c = nfs4lib.unixpath2comps("/src/hello.c")
    
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
        print >> sys.stderr, "\n  " + msg + ", ",

    def do_compound(self, *args, **kwargs):
        """Call ncl.compound. Handle all rpc.RPCExceptions as failures."""
        return self.failIfRaises(rpc.RPCException, self.ncl.compound, *args, **kwargs)

    def lookup_all_objects(self):
        """Generate a list of lookup operations with all types of objects"""
        result = []
        # FIXME: Add NF4ATTRDIR and NF4NAMEDATTR types. 
        for pathcomps in [self.normfile,
                          self.dirfile,
                          self.blockfile,
                          self.charfile,
                          self.linkfile,
                          self.socketfile,
                          self.fifofile]:
            result.append(self.ncl.lookup_op(pathcomps))

        return result

    def setUp(self):
        self.connect()
        self.putrootfhop = self.ncl.putrootfh_op()

    def get_invalid_fh(self):
        """Return a (guessed) invalid filehandle"""
        return nfs4lib.long2opaque(123456780, NFS4_FHSIZE/8)
    

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

    FIXME: Add attribute directory and named attribute testing. 

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
        lookupop = self.ncl.lookup_op(self.normfile)
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


class CloseTestCase(NFSTestCase):
    # FIXME
    pass
    

class CommitTestCase(NFSTestCase):
    """Test COMMIT operation.

    FIXME: Add attribute directory and named attribute testing. 

    Equivalence partitioning:

    Input Condition: current filehandle
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
        lookupop = self.ncl.lookup_op(self.normfile)

        # Offset = 0
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
        lookupop = self.ncl.lookup_op(self.normfile)
        
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
        lookupop = self.ncl.lookup_op(self.linkfile)
        commitop = self.ncl.commit_op(0, 0)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4ERR_INVAL)

    def testOnBlock(self):
        """COMMIT should fail with NFS4ERR_INVAL on block device
        
        Covered invalid equivalence classes: 3
        """
        lookupop = self.ncl.lookup_op(self.blockfile)
        commitop = self.ncl.commit_op(0, 0)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4ERR_INVAL)

    def testOnChar(self):
        """COMMIT should fail with NFS4ERR_INVAL on character device

        Covered invalid equivalence classes: 4
        """
        lookupop = self.ncl.lookup_op(self.charfile)
        commitop = self.ncl.commit_op(0, 0)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4ERR_INVAL)

    def testOnSocket(self):
        """COMMIT should fail with NFS4ERR_INVAL on socket

        Covered invalid equivalence classes: 5
        """
        lookupop = self.ncl.lookup_op(self.socketfile)
        commitop = self.ncl.commit_op(0, 0)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4ERR_INVAL)

    def testOnFifo(self):
        """COMMIT should fail with NFS4ERR_INVAL on FIFOs

        Covered invalid equivalence classes: 6
        """
        lookupop = self.ncl.lookup_op(self.fifofile)
        commitop = self.ncl.commit_op(0, 0)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4ERR_INVAL)
        
    def testOnDir(self):
        """COMMIT should fail with NFS4ERR_ISDIR on directories

        Covered invalid equivalence classes: 7
        """
        lookupop = self.ncl.lookup_op(self.dirfile)
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
        lookupop = self.ncl.lookup_op(self.normfile)
        
        commitop = self.ncl.commit_op(-1, -1)
        res = self.do_compound([self.putrootfhop, lookupop, commitop])
        self.failUnlessEqual(res.status, NFS4ERR_INVAL,
                             "no NFS4ERR_INVAL on overflow")


class CreateTestCase(NFSTestCase):
    """Test CREATE operation.

    FIXME: Add attribute directory and named attribute testing. 

    Equivalence partitioning:

    Input Condition: current filehandle
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
        NFSTestCase.setUp(self)
        self.obj_name = "object1"

        self.lookup_dir_op = self.ncl.lookup_op(self.tmp_dir)

    def _remove_object(self):
        # Make sure the object to create does not exist.
        # This cannot be done in setUp(), since assertion errors
        # are treated like errors (not failures). 
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
        self._remove_object()
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
        self._remove_object()
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
        self._remove_object()
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
        self._remove_object()
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
        self._remove_object()
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
        self._remove_object()
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
        self._remove_object()
        lookupop = self.ncl.lookup_op(self.normfile)
        
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
        self._remove_object()
        objtype = createtype4(self.ncl, type=NF4DIR)
        createop = self.ncl.create_op(self.obj_name, objtype)

        res = self.do_compound([createop])
        self.assert_status(res, [NFS4ERR_NOFILEHANDLE])

    def testZeroLengthName(self):
        """CREATE with zero length name should fail

        Covered invalid equivalence classes: 5
        """
        self._remove_object()
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
        self._remove_object()
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


class DelegpurgeTestCase(NFSTestCase):
    # FIXME
    pass


class DelegreturnTestCase(NFSTestCase):
    # FIXME
    pass


class GetattrTestCase(NFSTestCase):
    """Test GETATTR operation.

    FIXME: Add attribute directory and named attribute testing. 

    Equivalence partitioning:

    Input Condition: current filehandle
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
        lookupop = self.ncl.lookup_op(self.normfile)

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
        
        lookupop = self.ncl.lookup_op(self.normfile)
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
        lookupop = self.ncl.lookup_op(self.normfile)

        getattrop = self.ncl.getattr([1000])
        res = self.do_compound([self.putrootfhop, lookupop, getattrop])
        self.assert_OK(res)

    def testEmptyCall(self):
        """GETATTR should accept empty request

        Covered valid equivalence classes: 1, 9

        Comments: GETATTR should accept empty request
        """
        lookupop = self.ncl.lookup_op(self.normfile)

        getattrop = self.ncl.getattr([])
        res = self.do_compound([self.putrootfhop, lookupop, getattrop])
        self.assert_OK(res)

    def testSupported(self):
        """GETATTR(FATTR4_SUPPORTED_ATTRS) should return all mandatory

        Covered valid equivalence classes: 1, 9
        
        Comments: GETATTR(FATTR4_SUPPORTED_ATTRS) should return at
        least all mandatory attributes
        """
        lookupop = self.ncl.lookup_op(self.normfile)

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


class GetFhTestCase(NFSTestCase):
    """Test GETH operation

    FIXME: Add attribute directory and named attribute testing. 

    Equivalence partitioning:

    Input Condition: current filehandle
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
    """
    #
    # Testcases covering valid equivalence classes.
    #
    def testAllObjects(self):
        """GETFH on all type of objects

        Covered valid equivalence classes: 1, 2, 3, 4, 5, 6, 7
        """
        for lookupop in self.lookup_all_objects():
            getfhop = self.ncl.getfh_op()
            res = self.do_compound([self.putrootfhop, lookupop, getfhop])
            self.assert_OK(res)            
    #
    # Testcases covering invalid equivalence classes.
    #
    def testNoFh(self):
        """GETFH should fail with NFS4ERR_NOFILEHANDLE if no (cfh)

        Covered invalid equivalence classes: 8

        Comments: GETFH should fail with NFS4ERR_NOFILEHANDLE if no
        (cfh)
        """
        getfhop = self.ncl.getfh_op()
        res = self.do_compound([getfhop])
        self.assert_status(res, [NFS4ERR_NOFILEHANDLE])

class LinkTestCase(NFSTestCase):
    """Test LINK operation

    FIXME: Add attribute directory and named attribute testing.
    FIXME: More combintations of invalid filehandle types. 

    Equivalence partitioning:

    Input Condition: saved filehandle
        Valid equivalence classes:
            file(1)
            link(2)
            block(3)
            char(4)
            socket(5)
            FIFO(6)
        Invalid equivalence classes:
            dir(7)
            invalid filehandle(8)
    Input Condition: current filehandle
        Valid equivalence classes:
            dir(9)
        Invalid equivalence classes:
            not dir(10)
            invalid filehandle(11)
    Input Condition: newname
        Valid equivalence classes:
            valid name(12)
        Invalid equivalence classes:
            zerolength(13)

    Comments: It's not possible to cover eq. class 11, since saving a filehandle
    gives a current filehandle as well. 
    """

    def setUp(self):
        NFSTestCase.setUp(self)
        self.obj_name = "link1"

        self.lookup_dir_op = self.ncl.lookup_op(self.tmp_dir)

    def _remove_object(self):
        # Make sure the object to create does not exist.
        # This cannot be done in setUp(), since assertion errors
        # are treated like errors (not failures). 
        # This tests at the same time the REMOVE operation. Not much
        # we can do about it.
        operations = [self.ncl.putrootfh_op()]
        operations.append(self.lookup_dir_op)
        operations.append(self.ncl.remove_op(self.obj_name))

        res = self.do_compound(operations)
        self.assert_status(res, [NFS4_OK, NFS4ERR_NOENT])

    def _prepare_operation(self, pathcomps):
        # Put root FH
        operations = [self.putrootfhop]

        # Lookup source and save FH
        operations.append(self.ncl.lookup_op(pathcomps))
        operations.append(self.ncl.savefh_op())

        # Lookup target directory
        operations.append(self.putrootfhop)
        operations.append(self.lookup_dir_op)

        return operations
    
    #
    # Testcases covering valid equivalence classes.
    #
    def testFile(self):
        """LINK a regular file

        Covered valid equivalence classes: 1, 9, 12
        """
        self._remove_object()
        operations = self._prepare_operation(self.normfile)

        # Link operation
        linkop = self.ncl.link_op(self.obj_name)
        operations.append(linkop)
        res = self.do_compound(operations)
        self.assert_OK(res)

    def testLink(self):
        # FIXME: Is this allowed? See issue 118. Should the new link
        # be a link for the symlink itself, or the symlink target?
        """LINK a symbolic link

        Covered valid equivalence classes: 2, 9, 12
        """
        self._remove_object()
        operations = self._prepare_operation(self.linkfile)

        # Link operation
        linkop = self.ncl.link_op(self.obj_name)
        operations.append(linkop)
        res = self.do_compound(operations)
        self.assert_OK(res)

    def testBlock(self):
        """LINK a block device

        Covered valid equivalence classes: 3, 9, 12
        """
        self._remove_object()
        operations = self._prepare_operation(self.blockfile)

        # Link operation
        linkop = self.ncl.link_op(self.obj_name)
        operations.append(linkop)
        res = self.do_compound(operations)
        self.assert_OK(res)

    def testChar(self):
        """LINK a character device

        Covered valid equivalence classes: 4, 9, 12
        """
        self._remove_object()
        operations = self._prepare_operation(self.charfile)
        
        # Link operation
        linkop = self.ncl.link_op(self.obj_name)
        operations.append(linkop)
        res = self.do_compound(operations)
        self.assert_OK(res)

    def testSocket(self):
        """LINK a socket

        Covered valid equivalence classes: 5, 9, 12
        """
        self._remove_object()
        operations = self._prepare_operation(self.socketfile)
        
        # Link operation
        linkop = self.ncl.link_op(self.obj_name)
        operations.append(linkop)
        res = self.do_compound(operations)
        self.assert_OK(res)

    
    def testFIFO(self):
        """LINK a FIFO

        Covered valid equivalence classes: 6, 9, 12
        """
        self._remove_object()
        operations = self._prepare_operation(self.fifofile)
        
        # Link operation
        linkop = self.ncl.link_op(self.obj_name)
        operations.append(linkop)
        res = self.do_compound(operations)
        self.assert_OK(res)

    #
    # Testcases covering invalid equivalence classes.
    #

    def testDir(self):
        """LINK a directory should fail with NFS4ERR_ISDIR

        Covered invalid equivalence classes: 7
        """
        self._remove_object()
        operations = self._prepare_operation(self.dirfile)
        
        # Link operation
        linkop = self.ncl.link_op(self.obj_name)
        operations.append(linkop)
        res = self.do_compound(operations)
        self.assert_status(res, [NFS4ERR_ISDIR])

    def testNoSfh(self):
        """LINK should fail with NFS4ERR_NOFILEHANDLE if no (sfh)

        Covered invalid equivalence classes: 8

        Comments: LINK should fail with NFS4ERR_NOFILEHANDLE if no
        saved filehandle exists. 
        """
        linkop = self.ncl.link_op(self.obj_name)
        res = self.do_compound([self.putrootfhop, linkop])
        self.assert_status(res, [NFS4ERR_NOFILEHANDLE])

    def testCfhNotDir(self):
        """LINK should fail with NFS4ERR_NOTDIR if cfh is not dir

        Covered invalid equivalence classes: 10
        """
        self._remove_object()

        # Put root FH
        operations = [self.putrootfhop]

        # Lookup source and save FH
        operations.append(self.ncl.lookup_op(self.normfile))
        operations.append(self.ncl.savefh_op())

        # Lookup target directory (a file, this time)
        operations.append(self.putrootfhop)
        operations.append(self.ncl.lookup_op(self.normfile))

        # Link operation
        linkop = self.ncl.link_op(self.obj_name)
        operations.append(linkop)
        res = self.do_compound(operations)
        self.assert_status(res, [NFS4ERR_NOTDIR])

    def testZeroLengthName(self):
        """LINK with zero length new name should fail

        Covered invalid equivalence classes: 13
        """
        # CITI crashes on zero length names.
        # FIXME: remove return
        self.info_message("(DISABLED)")
        return
        
        self._remove_object()
        operations = self._prepare_operation(self.normfile)

        # Link operation
        linkop = self.ncl.link_op("")
        operations.append(linkop)
        res = self.do_compound(operations)
        self.assert_OK(res)


class LockTestCase(NFSTestCase):
    # FIXME
    pass


class LocktTestCase(NFSTestCase):
    # FIXME
    pass


class LockuTestCase(NFSTestCase):
    # FIXME
    pass

class LookupTestCase(NFSTestCase):
    """Test LOOKUP operation

    Equivalence partitioning:

    Input Condition: current filehandle
        Valid equivalence classes:
            dir(1)
        Invalid equivalence classes:
            not directory or symlink(2)
            invalid filehandle(3)
            symlink(12)
    Input Condition: filenames
        Valid equivalence classes:
            array of dirs(4)
            dirs + one non-dir(5)
            one non-dir(6)
        Invalid equivalence classes:
            array with non-existing components(7)
            array with non-accessable components(8)
            zero length array(9)
            array with non-utf8 components(10)
            array with non-dir components not last(11)
    """
    #
    # Testcases covering valid equivalence classes.
    #
    def testArrayOfDirs(self):
        """LOOKUP on array of directories

        Covered valid equivalence classes: 1, 4
        """
        lookupop = self.ncl.lookup_op(["doc", "porting"])
        res = self.do_compound([self.putrootfhop, lookupop])
        self.assert_OK(res)

    def testDirsNonDir(self):
        """LOOKUP on array of dirs + on non-dir

        Covered valid equivalence classes: 1, 5
        """
        lookupop = self.ncl.lookup_op(["doc", "porting", "TODO"])
        res = self.do_compound([self.putrootfhop, lookupop])
        self.assert_OK(res)

    def testNonDir(self):
        """LOOKUP simple non-dir object

        Covered valid equivalence classes: 1, 6
        """
        lookupop1 = self.ncl.lookup_op(["doc"])
        lookupop2 = self.ncl.lookup_op(["README"])
        res = self.do_compound([self.putrootfhop, lookupop1, lookupop2])
        self.assert_OK(res)

    #
    # Testcases covering invalid equivalence classes.
    #
    def testFhNotDir(self):
        """LOOKUP with non-dir (cfh) should give NFS4ERR_NOTDIR

        Covered invalid equivalence classes: 2
        """
        lookupop1 = self.ncl.lookup_op(["doc", "README"])
        lookupop2 = self.ncl.lookup_op(["porting"])
        res = self.do_compound([self.putrootfhop, lookupop1, lookupop2])
        self.assert_status(res, [NFS4ERR_NOTDIR])

    def testNoFh(self):
        """LOOKUP without (cfh) should return NFS4ERR_NOFILEHANDLE

        Covered invalid equivalence classes: 3
        """
        lookupop = self.ncl.lookup_op(["doc", "README"])
        res = self.do_compound([lookupop])
        self.assert_status(res, [NFS4ERR_NOFILEHANDLE])

    def testSymlinkFh(self):
        """LOOKUP with (cfh) as symlink should return NFS4ERR_SYMLINK

        Covered invalid equivalence classes: 12
        """
        lookupop1 = self.ncl.lookup_op(["src", "doc"])
        lookupop2 = self.ncl.lookup_op(["README"])
        res = self.do_compound([self.putrootfhop, lookupop1, lookupop2])
        self.assert_OK(res)

    def testNonExistent(self):
        """LOOKUP with non-existent components should return NFS4ERR_NOENT

        Covered invalid equivalence classes: 7
        """
        lookupop = self.ncl.lookup_op(["vapor_object"])
        res = self.do_compound([self.putrootfhop, lookupop])
        self.assert_status(res, [NFS4ERR_NOENT])

    def testNonAccessable(self):
        """LOOKUP with non-accessable components should return NFS4ERR_ACCES

        Covered invalid equivalence classes: 8
        """
        lookupop = self.ncl.lookup_op(["private", "info.txt"])
        res = self.do_compound([self.putrootfhop, lookupop])
        self.assert_status(res, [NFS4ERR_ACCES])

    def testZeroLengthPath(self):
        """LOOKUP with zero length array should return NFS4ERR_INVAL

        Covered invalid equivalence classes: 9
        """
        lookupop = self.ncl.lookup_op([])
        res = self.do_compound([self.putrootfhop, lookupop])
        self.assert_status(res, [NFS4ERR_INVAL])

    def testNonUTF8(self):
        """LOOKUP with non-UTF8 components should return NFS4ERR_INVAL

        Covered invalid equivalence classes: 10

        Comments: Not yet implemented. 
        """
        # FIXME: Implement
        self.info_message("(TEST NOT IMPLEMENTED)")

    def testNonDirNotLast(self):
        """LOOKUP with non-dir components not last should return NFS4ERR_NOTDIR

        Covered invalid equivalence classes: 11
        """
        lookupop = self.ncl.lookup_op(["doc", "README", "porting"])
        res = self.do_compound([self.putrootfhop, lookupop])
        self.assert_status(res, [NFS4ERR_NOTDIR])

    #
    # Misc. tests.
    #
    def testDots(self):
        """LOOKUP should not treat "." or ".." special

        Covered valid equivalence classes: 1, 5
        """
        lookupop = self.ncl.lookup_op(["doc", ".", "README"])
        res = self.do_compound([self.putrootfhop, lookupop])
        self.assert_status(res, [NFS4ERR_NOENT])

        lookupop = self.ncl.lookup_op(["doc", "porting", "..", "README"])
        res = self.do_compound([self.putrootfhop, lookupop])
        self.assert_status(res, [NFS4ERR_NOENT])


class LookuppTestCase(NFSTestCase):
    """Test LOOKUPP operation

    Equivalence partitioning:
        
    Input Condition: current filehandle
        Valid equivalence classes:
            symlink(10)
        Invalid equivalence classes:
            not symlink(2)
            invalid filehandle(3)
            symlink(12)


    """
    #
    # Testcases covering valid equivalence classes.
    #
    def testDir(self):
        """LOOKUPP with directory (cfh)

        Covered valid equivalence classes: 1
        """
        lookupop1 = self.ncl.lookup_op(["doc", "porting"])
        lookuppop = self.ncl.lookupp_op()
        lookupop2 = self.ncl.lookup_op(["README"])
        res = self.do_compound([self.putrootfhop, lookupop1, lookuppop, lookupop2])
        self.assert_OK(res)

    def testNamedAttrDir(self):
        """LOOKUPP with named attribute directory (cfh)

        Covered valid equivalence classes: 2

        Comments: Not yet implemented. 
        """
        # FIXME: Implement.
        self.info_message("(TEST NOT IMPLEMENTED)")

    #
    # Testcases covering invalid equivalence classes.
    #
    def testInvalidFh(self):
        """LOOKUPP with non-dir (cfh)

        Covered invalid equivalence classes: 3
        """
        lookupop = self.ncl.lookup_op(["doc", "README"])
        lookuppop = self.ncl.lookupp_op()
        res = self.do_compound([self.putrootfhop, lookupop, lookuppop])
        self.assert_status(res, [NFS4ERR_NOTDIR])

    #
    # Misc. tests.
    #
    def testAtRoot(self):
        """LOOKUPP with (cfh) at root should return NFS4ERR_NOENT

        Covered valid equivalence classes: 1
        """
        # CITI crashes on this one. 
        # FIXME: remove return
        self.info_message("(DISABLED)")
        return
    
        lookuppop = self.ncl.lookupp_op()
        res = self.do_compound([self.putrootfhop, lookuppop])
        self.assert_status(res, [NFS4ERR_NOTDIR])


class NverifyTestCase(NFSTestCase):
    """Test NVERIFY operation

    FIXME: Add attribute directory and named attribute testing. 

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
    Input Condition: fattr.attrmask
        Valid equivalence classes:
            valid attribute(9)
        Invalid equivalence classes:
            invalid attrmask(10) (FATTR4_*_SET)
    Input Condition: fattr.attr_vals
        Valid equivalence classes:
            changed attribute(11)
            same attribute(12)
        Invalid equivalence classes:
            -
    """
    #
    # Testcases covering valid equivalence classes.
    #
    def testChanged(self):
        """NVERIFY with CHANGED attribute should execute remaining ops

        Covered valid equivalence classes: 1, 2, 3, 4, 5, 6, 7, 9, 11
        """

        # Fetch sizes for all objects
        obj_sizes = []
        for lookupop in self.lookup_all_objects():
            getattrop = self.ncl.getattr([FATTR4_SIZE])
            res = self.do_compound([self.putrootfhop, lookupop, getattrop])
            self.assert_OK(res)
            obj = res.resarray[2].arm.arm.obj_attributes
            d =  nfs4lib.fattr2dict(obj)
            obj_sizes.append((lookupop, d["size"]))
        
        # For each type of object, do nverify with wrong filesize,
        # get new filesize and check if it match previous size. 
        for (lookupop, objsize) in obj_sizes:
            # Nverify op
            attrmask = nfs4lib.list2attrmask([FATTR4_SIZE])
            # We simulate a changed object by using a wrong filesize
            # Size attribute is 8 bytes. 
            attr_vals = nfs4lib.long2opaque(objsize + 17, 8)
            obj_attributes = nfs4lib.fattr4(self.ncl, attrmask, attr_vals)
            nverifyop = self.ncl.nverify_op(obj_attributes)

            # New getattr
            getattrop = self.ncl.getattr([FATTR4_SIZE])

            res = self.do_compound([self.putrootfhop, lookupop,
                                    nverifyop, getattrop])

            self.assert_OK(res)

            # Assert the new getattr was executed.
            # File sizes should match. 
            obj = res.resarray[-1].arm.arm.obj_attributes
            d =  nfs4lib.fattr2dict(obj)
            new_size = d["size"]
            self.failIf(objsize != new_size,
                        "GETATTR after NVERIFY returned different filesize")


    def testSame(self):
        """NVERIFY with unchanged attribute should return NFS4ERR_SAME

        Covered valid equivalence classes: 1, 2, 3, 4, 5, 6, 7, 9, 12
        """

        # Fetch sizes for all objects
        obj_sizes = []
        for lookupop in self.lookup_all_objects():
            getattrop = self.ncl.getattr([FATTR4_SIZE])
            res = self.do_compound([self.putrootfhop, lookupop, getattrop])
            self.assert_OK(res)
            obj = res.resarray[2].arm.arm.obj_attributes
            d =  nfs4lib.fattr2dict(obj)
            obj_sizes.append((lookupop, d["size"]))
        
        # For each type of object, do nverify with wrong filesize,
        # get new filesize and check if it match previous size. 
        for (lookupop, objsize) in obj_sizes:
            # Nverify op
            attrmask = nfs4lib.list2attrmask([FATTR4_SIZE])
            # Size attribute is 8 bytes. 
            attr_vals = nfs4lib.long2opaque(objsize, 8)
            obj_attributes = nfs4lib.fattr4(self.ncl, attrmask, attr_vals)
            nverifyop = self.ncl.nverify_op(obj_attributes)

            # New getattr
            getattrop = self.ncl.getattr([FATTR4_SIZE])

            res = self.do_compound([self.putrootfhop, lookupop,
                                    nverifyop, getattrop])

            self.assert_status(res, [NFS4ERR_SAME])

    #
    # Testcases covering invalid equivalence classes.
    #
    def testNoFh(self):
        """NVERIFY without (cfh) should return NFS4ERR_NOFILEHANDLE

        Covered invalid equivalence classes: 8
        """
        attrmask = nfs4lib.list2attrmask([FATTR4_SIZE])
        # Size attribute is 8 bytes. 
        attr_vals = nfs4lib.long2opaque(17, 8)
        obj_attributes = nfs4lib.fattr4(self.ncl, attrmask, attr_vals)
        nverifyop = self.ncl.nverify_op(obj_attributes)
        res = self.do_compound([nverifyop])
        self.assert_status(res, [NFS4ERR_NOFILEHANDLE])

    def testWriteOnlyAttributes(self):
        """NVERIFY with FATTR4_*_SET should return NFS4ERR_INVAL

        Covered invalid equivalence classes: 10

        Comments: See GetattrTestCase.testWriteOnlyAttributes. 
        """
        lookupop = self.ncl.lookup_op(self.normfile)

        # Nverify
        attrmask = nfs4lib.list2attrmask([FATTR4_TIME_ACCESS_SET])
        # Size attribute is 8 bytes. 
        attr_vals = nfs4lib.long2opaque(17, 8)
        obj_attributes = nfs4lib.fattr4(self.ncl, attrmask, attr_vals)
        nverifyop = self.ncl.nverify_op(obj_attributes)
        
        res = self.do_compound([self.putrootfhop, lookupop, nverifyop])
        self.assert_status(res, [NFS4ERR_INVAL])


class OpenTestCase(NFSTestCase):
    # FIXME
    pass

class OpenattrTestCase(NFSTestCase):
    """Test OPENATTR operation

    FIXME: Verify that these tests works, as soon as I have access to a server
    that supports named attributes. 

    Equivalence partitioning:

    Input Condition: current filehandle
        Valid equivalence classes:
            file(1)
            dir(2)
            block(3)
            char(4)
            link(5)
            socket(6)
            FIFO(7)
        Invalid equivalence classes:
            attribute directory(8)
            named attribute(9)
    """
    #
    # Testcases covering valid equivalence classes.
    #
    def testValid(self):
        """OPENATTR on all non-attribute objects

        Covered valid equivalence classes: 1, 2, 3, 4, 5, 6, 7
        """
        for lookupop in self.lookup_all_objects():
            openattrop = self.ncl.openattr_op()
            res = self.do_compound([self.putrootfhop, lookupop, openattrop])

            if res.status == NFS4ERR_NOTSUPP:
                op = lookupop.arm.path
                self.info_message("OPENATTR not supported on " + str(op))

            self.assert_status(res, [NFS4_OK, NFS4ERR_NOTSUPP])

    #
    # Testcases covering invalid equivalence classes.
    #
    def testOnAttrDir(self):
        """OPENATTR on attribute directory should fail with NFS4ERR_INVAL

        Covered invalid equivalence classes: 8
        """
        # Open attribute dir for root dir
        openattrop = self.ncl.openattr_op()
        res = self.do_compound([self.putrootfhop, openattrop])
        if res.status == NFS4ERR_NOTSUPP:
            self.info_message("OPENATTR not supported on /, cannot try this test")
            return

        openattrop1 = self.ncl.openattr_op()
        openattrop2 = self.ncl.openattr_op()
        res = self.do_compound([self.putrootfhop, openattrop1, openattrop2])
        self.assert_status(res, [NFS4ERR_INVAL])

    def testOnAttr(self):
        """OPENATTR on attribute should fail with NFS4ERR_INVAL

        Covered invalid equivalence classes: 9

        Comments: Not yet implemented. 
        """
        # Open attribute dir for doc/README
        lookupop = self.ncl.lookup_op(self.normfile)
        openattrop = self.ncl.openattr_op()
        res = self.do_compound([self.putrootfhop, lookupop, openattrop])

        if res.status == NFS4ERR_NOTSUPP:
            self.info_message("OPENATTR not supported on %s, cannot try this test" \
                              % self.normfile)
            return


        # FIXME: Implement rest of testcase.
        self.info_message("(TEST NOT IMPLEMENTED)")


class OpenconfirmTestCase(NFSTestCase):
    # FIXME
    pass

class OpendowngradeTestCase(NFSTestCase):
    # FIXME
    pass

class PutfhTestCase(NFSTestCase):
    """Test PUTFH operation

    FIXME: Add attribute directory and named attribute testing. 

    Equivalence partitioning:

    Input Condition: supplied filehandle
        Valid equivalence classes:
            file(1)
            dir(2)
            block(3)
            char(4)
            link(5)
            socket(6)
            FIFO(7)
            attribute directory(8)
            named attribute(9)
        Invalid equivalence classes:
            invalid filehandle(10)
    """
    #
    # Testcases covering valid equivalence classes.
    #
    def testAllObjects(self):
        """PUTFH followed by GETFH on all type of objects

        Covered valid equivalence classes: 1, 2, 3, 4, 5, 6, 7
        """
        # Fetch filehandles of all types
        # List with (objpath, fh)
        filehandles = []
        for lookupop in self.lookup_all_objects():
            getfhop = self.ncl.getfh_op()
            res = self.do_compound([self.putrootfhop, lookupop, getfhop])
            self.assert_OK(res)

            objpath = str(lookupop.arm.path)
            fh = res.resarray[-1].arm.arm.object
            filehandles.append((objpath, fh))

        # Try PUTFH & GETFH on all these filehandles. 
        for (objpath, fh) in filehandles:
            putfhop = self.ncl.putfh_op(fh)
            getfhop = self.ncl.getfh_op()
            res = self.do_compound([putfhop, getfhop])
            self.assert_OK(res)

            new_fh = res.resarray[-1].arm.arm.object
            self.failIf(new_fh != fh, "GETFH after PUTFH returned different fh")

    #
    # Testcases covering invalid equivalence classes.
    #
    def testInvalidFh(self):
        """PUTFH on (guessed) invalid filehandle should return NFS4ERR_STALE

        Covered invalid equivalence classes: 10
        """
        putfhop = self.ncl.putfh_op(self.get_invalid_fh())
        res = self.do_compound([putfhop])
        self.assert_status(res, [NFS4ERR_STALE])


class PutpubfhTestCase(NFSTestCase):
    """Test PUTPUBFH operation

    Equivalence partitioning:

    Input Condition: -
    
    """
    def testOp(self):
        """Testing PUTPUBFH

        Covered valid equivalence classes: -
        """
        putpubfhop = self.ncl.putpubfh_op()
        res = self.do_compound([putpubfhop])
        self.assert_OK(res)


class PutrootfhTestCase(NFSTestCase):
    """Test PUTROOTFH operation

    Equivalence partitioning:

    Input Condition: -
    """
    def testOp(self):
        """Testing PUTROOTFH

        Covered valid equivalence classes: -
        """
        putrootfhop = self.ncl.putrootfh_op()
        res = self.do_compound([putrootfhop])
        self.assert_OK(res)


class ReadTestCase(NFSTestCase):
    """Test READ operation

    FIXME: Add attribute directory and named attribute testing. 

    Equivalence partitioning:

    Input Condition: current filehandle
        Valid equivalence classes:
            file(1)
            named attribute(2)
        Invalid equivalence classes:
            dir(3)
            special device files(4)
            invalid filehandle(10)
    Input Condition: offset
        Valid equivalence classes:2
            zero(11)
            less than file size(12)
            greater than or equal to file size(13)
        Invalid equivalence classes:
            -
    Input Condition: count
        Valid equivalence classes:
            zero(14)
            one(15)
            greater than one(16)
        Invalid equivalence classes:
            -
    Input Condition: stateid
        Valid equivalence classes:
            all bits zero(17)
            all bits one(18)
            valid stateid from open(19)
        Invalid equivalence classes:
            invalid stateid(20)
    
    """
    #
    # Testcases covering valid equivalence classes.
    #
    def testSimpleRead(self):
        """READ from regular file with stateid=zeros

        Covered valid equivalence classes: 1, 11, 14, 17
        """
        lookupop = self.ncl.lookup_op(self.normfile)
        
        readop = self.ncl.read(offset=0, count=0, stateid=0)
        res = self.do_compound([self.putrootfhop, lookupop, readop])
        self.assert_OK(res)

    def testReadAttr(self):
        """READ from named attribute

        Covered valid equivalence classes: 2, 12, 16, 18
        """
        # FIXME: Implement rest of testcase.
        self.info_message("(TEST NOT IMPLEMENTED)")

    def testStateidOne(self):
        """READ with offset=2, count=1, stateid=ones

        Covered valid equivalence classes: 1, 12, 15, 18
        """
        lookupop = self.ncl.lookup_op(self.normfile)
        
        readop = self.ncl.read(offset=2, count=1, stateid=0xffffffffffffffffL)
        res = self.do_compound([self.putrootfhop, lookupop, readop])
        self.assert_OK(res)

    def testWithOpen(self):
        """READ with offset>size, count=5, stateid from OPEN

        Covered valid equivalence classes: 1, 13, 16, 19
        """
        # OPEN
        openop = self.ncl.open(file=self.normfile)
        getfhop = self.ncl.getfh_op()
        res = self.do_compound([self.putrootfhop, openop, getfhop])
        self.assert_OK(res)
        stateid = res.resarray[1].arm.arm.stateid
        fh = res.resarray[2].arm.arm.object
        
        # README is 36 bytes. Lets use 1000 as offset.
        putfhop = self.ncl.putfh_op(fh)
        readop = self.ncl.read(offset=1000, count=5, stateid=stateid)

        res = self.do_compound([putfhop, readop])
        self.assert_OK(res)

    #
    # Testcases covering invalid equivalence classes.
    #
    def testDirFh(self):
        """READ with (cfh)=directory should return NFS4ERR_ISDIR

        Covered invalid equivalence classes: 3
        """
        lookupop = self.ncl.lookup_op(self.dirfile)
        readop = self.ncl.read()

        res = self.do_compound([self.putrootfhop, lookupop, readop])
        self.assert_status(res, [NFS4ERR_ISDIR])

    def testSpecials(self):
        """READ with (cfh)=device files should return NFS4ERR_INVAL

        Covered invalid equivalence classes: 4
        """
        for pathcomps in [self.blockfile,
                          self.charfile,
                          self.linkfile,
                          self.socketfile,
                          self.fifofile]:
            lookupop = self.ncl.lookup_op(pathcomps)
            readop = self.ncl.read()

            res = self.do_compound([self.putrootfhop, lookupop, readop])

            if res.status != NFS4ERR_INVAL:
                self.info_message("READ on %s dit not return NFS4ERR_INVAL" % name)
            
            self.assert_status(res, [NFS4ERR_INVAL])

    def testNoFh(self):
        """READ without (cfh) should return NFS4ERR_NOFILEHANDLE

        Covered invalid equivalence classes: 10
        """
        readop = self.ncl.read()
        res = self.do_compound([readop])
        self.assert_status(res, [NFS4ERR_NOFILEHANDLE])

    def testInvalidStateid(self):
        """READ with a (guessed) invalid stateid should return NFS4ERR_STALE_STATEID

        Covered invalid equivalence classes: 20
        """
        readop = self.ncl.read(stateid=0x123456789L)
        res = self.do_compound([readop])
        self.assert_status(res, [NFS4ERR_STALE_STATEID])

        

class ReaddirTestCase(NFSTestCase):
    """Test READDIR operation

    FIXME: More testing of dircount/maxcount combinations.
    Note: maxcount represents READDIR4resok. Test this. 

    Equivalence partitioning:
        
    Input Condition: current filehandle
        Valid equivalence classes:
            dir(10)
        Invalid equivalence classes:
            not dir(11)
            no filehandle(12)
    Input Condition: cookie
        Valid equivalence classes:
            zero(20)
            nonzero valid cookie(21)
        Invalid equivalence classes:
            invalid cookie(22)
    Input Condition: cookieverf
        Valid equivalence classes:
            zero(30)
            nonzero valid verifier(31)
        Invalid equivalence classes:
            invalid verifier(32)
    Input Condition: dircount
        Valid equivalence classes:
            zero(40)
            nonzero(41)
        Invalid equivalence classes:
            -
    Input Condition: maxcount
        Valid equivalence classes:
            nonzero(50)
        Invalid equivalence classes:
            zero(51)
    Input Condition: attrbits
        Valid equivalence classes:
            all requests without FATTR4_*_SET (60)
        Invalid equivalence classes:
            requests with FATTR4_*_SET (61)
            
    """
    #
    # Testcases covering valid equivalence classes.
    #
    def testFirst(self):
        """READDIR with cookie=0, maxcount=4096

        Covered valid equivalence classes: 10, 20, 30, 40, 50, 60
        """        
        readdirop = self.ncl.readdir_op(cookie=0, cookieverf="\x00",
                                        dircount=0, maxcount=4096,
                                        attr_request=[])
        res = self.do_compound([self.putrootfhop, readdirop])
        self.assert_OK(res)
        
        
    def testSubsequent(self):
        """READDIR with cookie from previus call

        Covered valid equivalence classes: 10, 21, 31, 41, 50, 60
        """
        # FIXME: Implement rest of testcase, as soon as
        # CITI supports dircount/maxcount. 
        self.info_message("(TEST NOT IMPLEMENTED)")

        # Call READDIR with small maxcount, to make sure not all
        # entries are returned. Save cookie. 

        # Call READDIR a second time with saved cookie.

    #
    # Testcases covering invalid equivalence classes.
    #
    def testFhNotDir(self):
        """READDIR with non-dir (cfh) should give NFS4ERR_NOTDIR

        Covered invalid equivalence classes: 11
        """
        lookupop = self.ncl.lookup_op(["doc", "README"])
        readdirop = self.ncl.readdir_op(cookie=0, cookieverf="\x00",
                                        dircount=0, maxcount=4096,
                                        attr_request=[])
        res = self.do_compound([self.putrootfhop, lookupop, readdirop])
        self.assert_status(res, [NFS4ERR_NOTDIR])

    def testNoFh(self):
        """READDIR without (cfh) should return NFS4ERR_NOFILEHANDLE

        Covered invalid equivalence classes: 12
        """
        readdirop = self.ncl.readdir_op(cookie=0, cookieverf="\x00",
                                        dircount=0, maxcount=4096,
                                        attr_request=[])
        res = self.do_compound([readdirop])
        self.assert_status(res, [NFS4ERR_NOFILEHANDLE])

    def testInvalidCookie(self):
        """READDIR with invalid cookie should return NFS4ERR_BAD_COOKIE

        Covered invalid equivalence classes: 22
        """
        readdirop = self.ncl.readdir_op(cookie=1234567890, cookieverf="\x00",
                                        dircount=0, maxcount=4096,
                                        attr_request=[])
        res = self.do_compound([self.putrootfhop, readdirop])
        self.assert_status(res, [NFS4ERR_BAD_COOKIE])

    def testInvalidCookieverf(self):
        """READDIR with invalid cookieverf should return NFS4ERR_BAD_COOKIE

        Covered invalid equivalence classes: 32
        """
        # FIXME: Implement rest of testcase, as soon as
        # CITI supports dircount/maxcount. 
        self.info_message("(TEST NOT IMPLEMENTED)")

    def testMaxcountZero(self):
        """READDIR with maxcount=0 should return NFS4ERR_READDIR_NOSPC
        
        Covered invalid equivalence classes: 51
        """
        readdirop = self.ncl.readdir_op(cookie=0, cookieverf="\x00",
                                        dircount=0, maxcount=0,
                                        attr_request=[])
        res = self.do_compound([self.putrootfhop, readdirop])
        self.assert_status(res, [NFS4ERR_READDIR_NOSPC])

    def testWriteOnlyAttributes(self):
        """READDIR with attrs=FATTR4_*_SET should return NFS4ERR_INVAL

        Covered invalid equivalence classes: 61

        Comments: See GetattrTestCase.testWriteOnlyAttributes. 
        """
        attrmask = nfs4lib.list2attrmask([FATTR4_TIME_ACCESS_SET])
        readdirop = self.ncl.readdir_op(cookie=0, cookieverf="\x00",
                                        dircount=0, maxcount=4096,
                                        attr_request=attrmask)
        res = self.do_compound([self.putrootfhop, readdirop])
        self.assert_OK(res)
        self.assert_status(res, [NFS4ERR_INVAL])
        

    # FIXME: Misc. test: testa fattr4_rdattr_error kontra globalt fel. 

class ReadlinkTestCase(NFSTestCase):
    """Test READLINK operation

    Equivalence partitioning:

    Input Condition: current filehandle
        Valid equivalence classes:
            symlink(10)
        Invalid equivalence classes:
            not symlink or directory(11)
            directory(12)
            no filehandle(13)
    """
    #
    # Testcases covering valid equivalence classes.
    #
    def testReadlink(self):
        """READLINK on link

        Covered valid equivalence classes: 10
        """
        lookupop = self.ncl.lookup_op(["dev", "floppy"])
        readlinkop = self.ncl.readlink_op()
        res = self.do_compound([self.putrootfhop, lookupop, readlinkop])
        self.assert_OK(res)
        linkdata = res.resarray[2].arm.arm.link
        self.failIf(linkdata != "fd0",
                    "link data was %s, should be fd0" % linkdata)
    #
    # Testcases covering invalid equivalence classes.
    #
    def testFhNotSymlink(self):
        """READLINK on non-symlink objects should return NFS4ERR_INVAL

        Covered valid equivalence classes: 11
        """
        for pathcomps in [self.normfile,
                          self.blockfile,
                          self.charfile,
                          self.socketfile,
                          self.fifofile]:
            lookupop = self.ncl.lookup_op(pathcomps)
            readlinkop = self.ncl.readlink_op()

            res = self.do_compound([self.putrootfhop, lookupop, readlinkop])

            if res.status != NFS4ERR_INVAL:
                self.info_message("READLINK on %s dit not return NFS4ERR_INVAL" % name)
            
            self.assert_status(res, [NFS4ERR_INVAL])
            
    def testDirFh(self):
        """READLINK on a directory should return NFS4ERR_ISDIR

        Covered valid equivalence classes: 12
        """
        lookupop = self.ncl.lookup_op(self.dirfile)
        readlinkop = self.ncl.readlink_op()

        res = self.do_compound([self.putrootfhop, lookupop, readlinkop])
        self.assert_status(res, [NFS4ERR_ISDIR])
        

    def testNoFh(self):
        """READLINK without (cfh) should return NFS4ERR_NOFILEHANDLE

        Covered invalid equivalence classes: 13
        """
        readlinkop = self.ncl.readlink_op()
        res = self.do_compound([readlinkop])
        self.assert_status(res, [NFS4ERR_NOFILEHANDLE])
        
    

class RemoveTestCase(NFSTestCase):
    """Test REMOVE operation

    # FIXME: Test (OPEN, REMOVE, WRITE) etc. Wait for final decision. 

    Equivalence partitioning:

    Input Condition: current filehandle
        Valid equivalence classes:
            dir(10)
        Invalid equivalence classes:
            not dir(11)
            no filehandle(12)
    Input Condition: filename
        Valid equivalence classes:
            valid, existing name(20)
        Invalid equivalence classes:
            zerolength(21)
            non-utf8(22)
            non-existing name(23)
    """
    def setUp(self):
        NFSTestCase.setUp(self)
        self.obj_name = "object1"

        self.lookup_dir_op = self.ncl.lookup_op(self.tmp_dir)

    def _create_object(self):
        # Make sure we have something to remove. We create a directory, because
        # it's simple.
        objtype = createtype4(self.ncl, type=NF4DIR)
        createop = self.ncl.create_op(self.obj_name, objtype)
        res = self.do_compound([self.putrootfhop, self.lookup_dir_op, createop])

        self.assert_status(res, [NFS4_OK, NFS4ERR_EXIST])

    #
    # Testcases covering valid equivalence classes.
    #
    def testValid(self):
        """Valid REMOVE on existing object

        Covered valid equivalence classes: 10, 20
        """
        self._create_object()
        removeop = self.ncl.remove_op(self.obj_name)
        res = self.do_compound([self.putrootfhop, self.lookup_dir_op, removeop])

        self.assert_OK(res)

    #
    # Testcases covering invalid equivalence classes.
    #
    def testFhNotDir(self):
        """REMOVE with non-dir (cfh) should give NFS4ERR_NOTDIR

        Covered invalid equivalence classes: 11
        """
        lookupop = self.ncl.lookup_op(self.normfile)
        removeop = self.ncl.remove_op(self.obj_name)
        res = self.do_compound([self.putrootfhop, lookupop, removeop])

        self.assert_status(res, [NFS4ERR_NOTDIR])

    def testNoFh(self):
        """REMOVE without (cfh) should return NFS4ERR_NOFILEHANDLE

        Covered invalid equivalence classes: 12
        """
        removeop = self.ncl.remove_op(self.obj_name)
        res = self.do_compound([removeop])
        self.assert_status(res, [NFS4ERR_NOFILEHANDLE])

    def testZeroLengthTarget(self):
        """REMOVE with zero length target should return NFS4ERR_INVAL

        Covered invalid equivalence classes: 21
        """
        self._create_object()

        removeop = self.ncl.remove_op("")
        res = self.do_compound([self.putrootfhop, self.lookup_dir_op, removeop])

        self.assert_status(res, [NFS4ERR_INVAL])

    def testNonUTF8(self):
        """REMOVE with non-UTF8 components should return NFS4ERR_INVAL

        Covered invalid equivalence classes: 22

        Comments: Not yet implemented. 
        """
        # FIXME: Implement
        self.info_message("(TEST NOT IMPLEMENTED)")

    def testNonExistent(self):
        """REMOVE on non-existing object should return NFS4ERR_NOENT

        Covered invalid equivalence classes: 23
        """
        removeop = self.ncl.remove_op("vapor_object")
        res = self.do_compound([self.putrootfhop, self.lookup_dir_op, removeop])

        self.assert_status(res, [NFS4ERR_NOENT])
        

class RenameTestCase(NFSTestCase):
    """Test RENAME operation

    FIXME: Test renaming of a named attribute
    to be a regular file and vice versa.

    Equivalence partitioning:

    Input Condition: saved filehandle
        Valid equivalence classes:
            dir(10)
        Invalid equivalence classes:
            non-dir(11)
            no filehandle(12)
            invalid filehandle(13)
    Input Condition: oldname
        Valid equivalence classes:
            valid name(20)
        Invalid equivalence classes:
            non-existent name(21)
            zerolength(22)
            non-utf8(23)
    Input Condition: current filehandle
        Valid equivalence classes:
            dir(30)
        Invalid equivalence classes:
            non-dir(31)
            no filehandle(32)
            invalid filehandle(33)
    Input Condition: newname
        Valid equivalence classes:
            valid name(40)
        Invalid equivalence classes:
            zerolength(41)
            non-utf8(42)

    Comments: It's not possible to cover eq. class 32, since saving a filehandle
    gives a current filehandle as well. 
    """
    def setUp(self):
        NFSTestCase.setUp(self)
        self.oldname = "object1"
        self.newname = "object2"

        self.lookup_dir_op = self.ncl.lookup_op(self.tmp_dir)

    def _create_object(self):
        # Make sure we have something to rename. We create a directory, because
        # it's simple.
        objtype = createtype4(self.ncl, type=NF4DIR)
        createop = self.ncl.create_op(self.oldname, objtype)
        res = self.do_compound([self.putrootfhop, self.lookup_dir_op, createop])

        self.assert_status(res, [NFS4_OK, NFS4ERR_EXIST])

    def _prepare_operation(self):
        operations = [self.putrootfhop]
        
        # Lookup source and save FH
        operations.append(self.lookup_dir_op)
        operations.append(self.ncl.savefh_op())

        # Lookup target directory
        operations.append(self.putrootfhop)
        operations.append(self.lookup_dir_op)

        return operations

    #
    # Testcases covering valid equivalence classes.
    #
    def testValid(self):
        """Test valid RENAME operation

        Covered valid equivalence classes: 10, 20, 30, 40
        """
        self._create_object()

        operations = self._prepare_operation()

        # Rename
        renameop = self.ncl.rename_op(self.oldname, self.newname)
        operations.append(renameop)
        res = self.do_compound(operations)
        self.assert_OK(res)

    #
    # Testcases covering invalid equivalence classes.
    #
    def testSfhNotDir(self):
        """RENAME with non-dir (sfh) should return NFS4ERR_NOTDIR

        Covered invalid equivalence classes: 11
        """
        operations = [self.putrootfhop]
        
        # Lookup source and save FH
        operations.append(self.ncl.lookup_op(self.normfile))
        operations.append(self.ncl.savefh_op())

        # Lookup target directory
        operations.append(self.putrootfhop)
        operations.append(self.lookup_dir_op)

        # Rename
        renameop = self.ncl.rename_op(self.oldname, self.newname)
        operations.append(renameop)
        res = self.do_compound(operations)
        self.assert_status(res, [NFS4ERR_NOTDIR])

    def testNoSfh(self):
        """RENAME without (sfh) should return NFS4ERR_NOFILEHANDLE

        Covered invalid equivalence classes: 12
        """
        # Lookup target directory
        operations = [self.putrootfhop]
        operations.append(self.lookup_dir_op)
        
        # Rename
        renameop = self.ncl.rename_op(self.oldname, self.newname)
        operations.append(renameop)
        res = self.do_compound(operations)
        self.assert_status(res, [NFS4ERR_NOFILEHANDLE])

    # FIXME: Cover eq. class 13.

    def testNonExistent(self):
        """RENAME on non-existing object should return NFS4ERR_NOENT

        Covered invalid equivalence classes: 21
        """
        self._create_object()
        operations = self._prepare_operation()

        # Rename
        renameop = self.ncl.rename_op("vapor_object", self.newname)
        operations.append(renameop)
        res = self.do_compound(operations)
        self.assert_status(res, [NFS4ERR_NOENT])

    def testZeroLengthOldname(self):
        """RENAME with zero length oldname should return NFS4ERR_INVAL

        Covered invalid equivalence classes: 22
        """
        self._create_object()
        operations = self._prepare_operation()

        # Rename
        renameop = self.ncl.rename_op("", self.newname)
        operations.append(renameop)
        res = self.do_compound(operations)
        self.assert_status(res, [NFS4ERR_INVAL])

    # FIXME: Cover eq. class 23. 
        
    def testCfhNotDir(self):
        """RENAME with non-dir (cfh) should return NFS4ERR_NOTDIR

        Covered invalid equivalence classes: 31
        """
        operations = [self.putrootfhop]
        
        # Lookup source and save FH
        operations.append(self.lookup_dir_op)
        operations.append(self.ncl.savefh_op())

        # Lookup target directory
        operations.append(self.putrootfhop)
        operations.append(self.ncl.lookup_op(self.normfile))

        # Rename
        renameop = self.ncl.rename_op(self.oldname, self.newname)
        operations.append(renameop)
        res = self.do_compound(operations)
        self.assert_status(res, [NFS4ERR_NOTDIR])

    # FIXME: Cover eq. class 33.
    
    def testZeroLengthNewname(self):
        """RENAME with zero length newname should return NFS4ERR_INVAL

        Covered invalid equivalence classes: 41
        """
        self._create_object()
        operations = self._prepare_operation()

        # Rename
        renameop = self.ncl.rename_op(self.oldname, "")
        operations.append(renameop)
        res = self.do_compound(operations)
        self.assert_status(res, [NFS4ERR_INVAL])
    
    # FIXME: Cover eq. class 42.     

class RenewTestCase(NFSTestCase):
    # FIXME
    pass

class RestorefhTestCase(NFSTestCase):
    """Test RESTOREFH operation

    Equivalence partitioning:

    Input Condition: saved filehandle
        Valid equivalence classes:
            valid filehandle(10)
        Invalid equivalence classes:
            no filehandle(11)

    Comments: We do not test restoration of a invalid filehandle,
    since it's hard to save one. It's not possible to PUTFH an invalid
    filehandle, for example.
    """
    #
    # Testcases covering valid equivalence classes.
    #
    def testValid(self):
        """SAVEFH and RESTOREFH

        Covered equivalence classes: 10

        Comments: Also tests SAVEFH operation. 
        """
        # The idea is to use a sequence of operations like this:
        # PUTROOTFH, LOOKUP, GETFH#1, SAVEFH, LOOKUP, RESTOREFH, GETH#2.
        # If this procedure succeeds and result from GETFH#1 and GETFH#2 match,
        # things should be OK.

        # Lookup a file, get and save FH. 
        operations = [self.putrootfhop]
        operations.append(self.ncl.lookup_op(self.normfile))
        operations.append(self.ncl.getfh_op())
        operations.append(self.ncl.savefh_op())

        # Lookup another file.
        operations.append(self.putrootfhop)
        operations.append(self.ncl.lookup_op(self.hello_c))

        # Restore saved fh and get fh. 
        operations.append(self.ncl.restorefh_op())
        operations.append(self.ncl.getfh_op())
        
        res = self.do_compound(operations)
        self.assert_OK(res)

        fh1 = res.resarray[2].arm.arm.object
        fh2 = res.resarray[7].arm.arm.object 
        self.failIf(fh1 != fh2, "restored FH does not match saved FH")

    #
    # Testcases covering invalid equivalence classes.
    #
    def testNoFh(self):
        """RESTOREFH without (sfh) should return NFS4ERR_NOFILEHANDLE

        Covered invalid equivalence classes: 11
        """
        res = self.do_compound([self.ncl.restorefh_op()])
        self.assert_status(res, [NFS4ERR_NOFILEHANDLE])
        

class SavefhTestCase(NFSTestCase):
    """Test SAVEFH operation

    Equivalence partitioning:

    Input Condition: current filehandle
        Valid equivalence classes:
            valid filehandle(10)
        Invalid equivalence classes:
            no filehandle(11)

    Comments: Equivalence class 10 is covered by
    RestorefhTestCase.testValid.
    """
    #
    # Testcases covering invalid equivalence classes.
    #
    def testNoFh(self):
        """SAVEFH without (cfh) should return NFS4ERR_NOFILEHANDLE

        Covered invalid equivalence classes: 11
        """
        res = self.do_compound([self.ncl.savefh_op()])
        self.assert_status(res, [NFS4ERR_NOFILEHANDLE])
    

class SecinfoTestCase(NFSTestCase):
    """Test SECINFO operation

    Equivalence partitioning:

    Input Condition: current filehandle
        Valid equivalence classes:
            dir(10)
        Invalid equivalence classes:
            not dir(11)
            invalid filehandle(12)
    Input Condition: name
        Valid equivalence classes:
            valid name(20)
        Invalid equivalence classes:
            non-existent object(21)
            zerolength(22)
            non-utf8(23)

    Comments: It's hard to cover eq. class 12, since it's not possible
    PUTFH an invalid filehandle. 
    """
    #
    # Testcases covering valid equivalence classes.
    #
    def testValid(self):
        """SECINFO on existing file

        Covered equivalence classes: 10, 20
        """
        lookupop = self.ncl.lookup_op(["doc"])
        secinfoop = self.ncl.secinfo_op("README")

        res = self.do_compound([self.putrootfhop, lookupop, secinfoop])
        self.assert_OK(res)

        # Make sure at least one security mechanisms is returned.
        mechanisms = res.resarray[-1].arm.arm
        self.failIf(len(mechanisms) < 1,
                    "SECINFO returned no security mechanisms")

    #
    # Testcases covering invalid equivalence classes.
    #
    def testFhNotDir(self):
        """SECINFO with non-dir (cfh) should give NFS4ERR_NOTDIR

        Covered invalid equivalence classes: 11
        """
        lookupop = self.ncl.lookup_op(self.normfile)
        secinfoop = self.ncl.secinfo_op("README")

        res = self.do_compound([self.putrootfhop, lookupop, secinfoop])
        self.assert_status(res, [NFS4ERR_NOTDIR])

    def testNonExistent(self):
        """SECINFO on non-existing object should return NFS4ERR_NOENT

        Covered invalid equivalence classes: 21
        """
        lookupop = self.ncl.lookup_op(["doc"])
        secinfoop = self.ncl.secinfo_op("vapor_object")

        res = self.do_compound([self.putrootfhop, lookupop, secinfoop])
        self.assert_status(res, [NFS4ERR_NOENT])

    def testZeroLengthName(self):
        """SECINFO with zero length name should return NFS4ERR_INVAL

        Covered invalid equivalence classes: 22
        """
        lookupop = self.ncl.lookup_op(["doc"])
        secinfoop = self.ncl.secinfo_op("")

        res = self.do_compound([self.putrootfhop, lookupop, secinfoop])
        self.assert_status(res, [NFS4ERR_INVAL])

    def testNonUTF8(self):
        """SECINFO with non-UTF8 name should return NFS4ERR_INVAL

        Covered invalid equivalence classes: 23

        Comments: Not yet implemented. 
        """
        # FIXME: Implement
        self.info_message("(TEST NOT IMPLEMENTED)")

        

class SetattrTestCase(NFSTestCase):
    # FIXME
    pass

class SetclientidTestCase(NFSTestCase):
    # FIXME
    pass

class SetclientidconfirmTestCase(NFSTestCase):
    # FIXME
    pass

class VerifyTestCase(NFSTestCase):
    # FIXME
    pass

class WriteTestCase(NFSTestCase):
    # FIXME
    pass


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
