#!/usr/bin/env python2

# nfs4lib.py - NFS4 library for Python. 
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


NFS_PROGRAM = 100003
NFS_VERSION = 4
NFS_PORT = 2049

import rpc
from nfs4constants import *
from nfs4types import *
import random
import array
import socket
import os

class PartialNFS4Client:
    def addpackers(self):
        self.packer = rpc.Packer()
        self.unpacker = rpc.Unpacker('')

    def null(self):
	return self.make_call(0, None, None, None)

    def compound(self, argarray, tag="", minorversion=0):
        """A Compound call"""
        compoundargs = COMPOUND4args(self, argarray=argarray, tag=tag, minorversion=minorversion)
        res = COMPOUND4res(self)
        
        self.make_call(1, None, compoundargs.pack, res.unpack)
        return res

    #
    # Utility methods
    #
    def gen_random_64(self):
        a = array.array('I')
        for turn in range(4):
            a.append(random.randrange(2**16))
        return a.tostring()

    def gen_uniq_id(self):
        # Use FQDN and pid as ID.
        return socket.gethostname() + str(os.getpid())

    #
    # Operations
    #

    def getfh(self):
        return nfs_argop4(self, argop=OP_GETFH)

    def putrootfh(self):
        return nfs_argop4(self, argop=OP_PUTROOTFH)

    def setclientid(self, verifier=None, id=None, cb_program=None, r_netid=None, r_addr=None, ):
        if not verifier:
            verifier = self.gen_random_64()

        if not id:
            id = self.gen_uniq_id()

        if not cb_program:
            # FIXME
            cb_program = 0

        if not r_netid:
            # FIXME
            r_netid = "udp"

        if not r_addr:
            # FIXME
            r_addr = socket.gethostname()
        
        client_id = nfs_client_id4(self, verifier=verifier, id=id)
        cb_location = clientaddr4(self, r_netid=r_netid, r_addr=r_addr)
        callback = cb_client4(self, cb_program=cb_program, cb_location=cb_location)
        opsetclientid = SETCLIENTID4args(self, client=client_id, callback=callback)

        return nfs_argop4(self, argop=OP_SETCLIENTID, opsetclientid=opsetclientid)
    

class UDPNFS4Client(PartialNFS4Client, rpc.RawUDPClient):
    def __init__(self, host):
        rpc.RawUDPClient.__init__(self, host, NFS_PROGRAM, NFS_VERSION, NFS_PORT)

    def mkcred(self):
	if self.cred == None:
	    self.cred = (rpc.AUTH_UNIX, rpc.make_auth_unix(1, "maggie.lkpg.cendio.se", 0, 0, [0, 1, 2, 3, 4, 6, 10]))
	return self.cred

    def mkverf(self):
	if self.verf == None:
	    self.verf = (rpc.AUTH_NULL, rpc.make_auth_null())
	return self.verf


class TCPNFS4Client(PartialNFS4Client, rpc.RawTCPClient):
    def __init__(self, host):
        rpc.RawTCPClient.__init__(self, host, NFS_PROGRAM, NFS_VERSION, NFS_PORT)



if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print "Usage: %s <protocol> <host>" % sys.argv[0]
        sys.exit(1)
    
    proto = sys.argv[1]
    host = sys.argv[2]
    if proto == "tcp":
        ncl = TCPNFS4Client(host)
    elif proto == "udp":
        ncl = UDPNFS4Client(host)
    else:
        raise RuntimeError, "Wrong protocol"

    # PUTROOT & GETFH
    putrootfhoperation = nfs_argop4(ncl, argop=OP_PUTROOTFH)
    getfhoperation = nfs_argop4(ncl, argop=OP_GETFH)
    
    res =  ncl.compound([putrootfhoperation, getfhoperation])

    fh = res.resarray[1].opgetfh.resok4.object
    print "fh is", repr(fh)



