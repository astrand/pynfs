
all: nfs4constants.py nfs4types.py nfs4packer.py

nfs4constants.py nfs4types.py nfs4packer.py: nfs4.x rpcsec_gss.x
	./rpcgen.py nfs4.x rpcsec_gss.x
