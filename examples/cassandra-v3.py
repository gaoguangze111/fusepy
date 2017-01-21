#!/usr/bin/env python
from __future__ import print_function, absolute_import, division

import logging

#HashCode Library
import mmh3

#cassandra API
import pycassa
#persistent files (metadata) 
import json
import mmh3
import pickle


#parallel the programme
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed, wait
from time import sleep



from collections import defaultdict
from errno import ENOENT
from stat import S_IFDIR, S_IFLNK, S_IFREG
from sys import argv, exit
from time import time


from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

if not hasattr(__builtins__, 'bytes'):
    bytes = str

def read_multi(block_hash, i):
    col_fam = Cassandra.static_col_fam
    #pool = pycassa.pool.ConnectionPool('TestKeySpace')
    #col_fam = pycassa.columnfamily.ColumnFamily(pool, 'ColumnFamily')
    #print("####### Read Process: "+str(i))
    #block_hash = self.col_fam.get(path, columns = [str(i+nbBlock)])[str(i+nbBlock)]
    s = col_fam.get(block_hash, columns = ["content"])["content"]
    #print("####### end Read: "+ s + "  HahsCode:" + str(block_hash))
    #return (i, col_fam.get(block_hash, columns = ["content"])["content"])
    return (i, s)

def write_multi(block_hash, content):
    col_fam = Cassandra.static_col_fam
    #pool = pycassa.pool.ConnectionPool('TestKeySpace')
    #col_fam = pycassa.columnfamily.ColumnFamily(pool, 'ColumnFamily')
    print("******* begin insert")
    print("Content: "+content)
    print("HashCode: "+str(block_hash))
    col_fam.insert(str(block_hash), {'content': content})
    print("****** end insert")
    return "end "+ str(col_fam.get(str(block_hash)))
    #return 8



class Cassandra(LoggingMixIn, Operations):
    'Example memory filesystem. Supports only one level of files.'
    static_pool = pycassa.pool.ConnectionPool('TestKeySpace')
    static_col_fam = pycassa.columnfamily.ColumnFamily(static_pool, 'ColumnFamily')
    def __init__(self):
        self.files = {}
        self.data = defaultdict(bytes)
        self.fd = 0
        self.sizeBlock = 4
        now = time()

        #initialize cassandra
        Cassandra.pool = pycassa.pool.ConnectionPool('TestKeySpace')
        Cassandra.col_fam = pycassa.columnfamily.ColumnFamily(self.pool, 'ColumnFamily')
        
        self.pool = pycassa.pool.ConnectionPool('TestKeySpace')
        self.col_fam = pycassa.columnfamily.ColumnFamily(self.pool, 'ColumnFamily')
        try:
            files_json = self.col_fam.get('files', columns=['metadata'])['metadata']
            self.files = json.loads(files_json)
        except:
            #self.files = {}
            self.files['/'] = dict(st_mode=(S_IFDIR | 0o755), st_ctime=now, st_mtime=now, st_atime=now, st_nlink=2)

    def chmod(self, path, mode):
        self.files[path]['st_mode'] &= 0o770000
        self.files[path]['st_mode'] |= mode
        return 0

    def chown(self, path, uid, gid):
        self.files[path]['st_uid'] = uid
        self.files[path]['st_gid'] = gid

    def create(self, path, mode):
        self.files[path] = dict(st_mode=(S_IFREG | mode), st_nlink=1,
                                st_size=0, st_ctime=time(), st_mtime=time(),
                                st_atime=time())

        self.fd += 1
        return self.fd

    def getattr(self, path, fh=None):
        if path not in self.files:
            raise FuseOSError(ENOENT)

        return self.files[path]

    def getxattr(self, path, name, position=0):
        attrs = self.files[path].get('attrs', {})

        try:
            return attrs[name]
        except KeyError:
            return ''       # Should return ENOATTR

    def listxattr(self, path):
        attrs = self.files[path].get('attrs', {})
        return attrs.keys()

    def mkdir(self, path, mode):
        self.files[path] = dict(st_mode=(S_IFDIR | mode), st_nlink=2,
                                st_size=0, st_ctime=time(), st_mtime=time(),
                                st_atime=time())

        self.files['/']['st_nlink'] += 1

    def open(self, path, flags):
        self.fd += 1
        return self.fd

    def read(self, path, size, offset, fh):

        

        size = self.files[path]["st_size"]
        sizeBlock = self.sizeBlock
        nbBlock = offset // sizeBlock
        lenData = size
        rest = sizeBlock - offset % sizeBlock
        if (rest == sizeBlock):
            rest = 0
        nbNewBlocks = (lenData-rest)//sizeBlock

        result2 = ""
        
        
        pool = ProcessPoolExecutor(4)
        futures = []
        resultList = []

        #fileData
        #fileData = self.col_fam.get(path)
        #print("####### fileData" + str(fileData))
        if(rest == 0):
            i = 0
            while(i < nbNewBlocks):
                #Get the hashcode ----> get the content with hashcode!!
                block_hash = self.col_fam.get(path, columns = [str(i+nbBlock)])[str(i+nbBlock)]
                #block_hash = fileData[str(i+nbBlock)]
                #result2 = result2 + self.col_fam.get(block_hash, columns = ["content"])["content"]
                futures.append(pool.submit(read_multi, block_hash, i))
                i = i+1

            #Get results and combien results
            wait(futures)
            for x in as_completed(futures):
                try:
                    print("###### result " +str(x.result()))
                    resultList.append(x.result())
                except Exception as exc:
                    print("exception ......."+ str(exc))

            resultList.sort(key= lambda resultItem: resultItem[0])
            for item in resultList:
                result2 = result2 + item[1]

            if(lenData > nbNewBlocks * sizeBlock):
                block_hash = self.col_fam.get(path, columns = [str(nbNewBlocks+nbBlock)])[str(nbNewBlocks+nbBlock)]
                #block_hash = fileData[str(nbNewBlocks+nbBlock)]
                result2 = result2 + self.col_fam.get(block_hash, columns = ["content"])["content"]
        else:

            block_hash = self.col_fam.get(path, columns=[str(nbBlock)])[str(nbBlock)]
            #block_hash = fileData[str(nbBlock)]
            tmp = self.col_fam.get(block_hash, columns = ["content"])["content"]
            result2 = tmp[-rest:]
            i = 0
            while(i < nbNewBlocks):
                block_hash = self.col_fam.get(path, columns = [str(i+nbBlock+1)])[str(i+nbBlock+1)]
                #result2 = result2 + self.col_fam.get(block_hash, columns = ["content"])["content"]
                #block_hash = fileData[str(i+nbBlock+1)]
                futures.append(pool.submit(read_multi, block_hash, i))
                i = i+1
            #Get results and combine results
            for x in as_completed(futures):
                resultList.append(x.result())
            resultList.sort(key= lambda resultItem: resultItem[0])
            for item in resultList:
                result2 = result2 + item[1]

            if(lenData > rest + nbNewBlocks*sizeBlock):
                block_hash = self.col_fam.get(path, columns = [str(nbNewBlocks+nbBlock+1)])[str(nbNewBlocks+nbBlock+1)]
                #block_hash = fileData[str(nbNewBlocks+nbBlock+1)]
                result2 = result2 + self.col_fam.get(block_hash, columns = ["content"])["content"]
                        

        return result2

    def readdir(self, path, fh):
        return ['.', '..'] + [x[1:] for x in self.files if x != '/']

    def readlink(self, path):
        # TODO
        # read from cassandra in an array
        # return (part of) array
        file=self.col_fam.get(path, columns=["content"])
        self.data[path] = file["content"]
        return self.data[path]

    def removexattr(self, path, name):
        attrs = self.files[path].get('attrs', {})

        try:
            del attrs[name]
        except KeyError:
            pass        # Should return ENOATTR

    def rename(self, old, new):
        self.files[new] = self.files.pop(old)

    def rmdir(self, path):
        self.files.pop(path)
        self.files['/']['st_nlink'] -= 1

    def setxattr(self, path, name, value, options, position=0):
        # Ignore options
        attrs = self.files[path].setdefault('attrs', {})
        attrs[name] = value

    def statfs(self, path):
        return dict(f_bsize=512, f_blocks=4096, f_bavail=2048)

    def symlink(self, target, source):
        self.files[target] = dict(st_mode=(S_IFLNK | 0o777), st_nlink=1,
                                  st_size=len(source))

        # TODO to update
        self.data[target] = source
        #cassandra
        self.col_fam.insert(target, {"content": self.data[target]})
        self.col_fam.insert("files", {"metadata": json.dumps(self.files)})

    def truncate(self, path, length, fh=None):
        # TODO truncate the file on Cassandra
        self.data[path] = self.data[path][:length]
        self.files[path]['st_size'] = length
        #cassandra
        self.col_fam.insert(path, {"content": self.data[path]})
        self.col_fam.insert("files", {"metadata": json.dumps(self.files)})

    def unlink(self, path):
        self.files.pop(path)

    def utimens(self, path, times=None):
        now = time()
        atime, mtime = times if times else (now, now)
        self.files[path]['st_atime'] = atime
        self.files[path]['st_mtime'] = mtime

    def write(self, path, data, offset, fh):
        #function to multi threads
        



        #print("#### offset: "+ str(offset))
        # TODO write the file on Cassandra
        #self.data[path] = self.data[path][:offset] + data

        #self.files[path]['st_size'] = len(self.data[path])
        self.files[path]['st_size'] = offset + len(data)

        #Define the size of Block
        sizeBlock = self.sizeBlock

        #Get which block to write
        nbBlock = offset // sizeBlock
        lenData = len(data)
        rest = sizeBlock - offset % sizeBlock
        if (rest == sizeBlock):
            rest = 0
        #Get how many blokcs needed to insert    
        nbNewBlocks = (lenData-rest)//sizeBlock
        
        #tmp_col = self.col_fam
        #col_fam_string = pickle.dumps(tmp_col)
        #multithread pool
        pool = ProcessPoolExecutor(4)
        futures = []

        start = time();
        print("####### Rest: "+ str(rest)+" LenthData:"+ str(lenData) + " offeset:"+str(offset)+"  nbNewblock"+str(nbNewBlocks))
        if(rest == 0):  
        # Get the block---> Generate the HashCode--->Save HashCode---->Save content
            i = 0
            print("###### i: "+ str(i) + "   nbNewBlocks: "+ str(nbNewBlocks))
            while(i < nbNewBlocks):          #paralle
                content =data[(i*sizeBlock):((i+1)*sizeBlock)]
                block_hash = mmh3.hash64(content) 
                self.col_fam.insert(path, {str(i+nbBlock): str(block_hash)})

                print("######### " +str(i) +" submit begin!!!")
                futures.append(pool.submit(write_multi, block_hash, content))
                print("######### " +str(i) +" submit end!!!")
                i = i+1
            #wait(futures)

            if(lenData > nbNewBlocks * sizeBlock): #examine if need to insert a non-complete block
                content = data[(nbNewBlocks*sizeBlock):]
                block_hash = mmh3.hash64(content)
                self.col_fam.insert(path, {str(nbNewBlocks+nbBlock): str(block_hash)})
                self.col_fam.insert(str(block_hash), {"content": content})
                #print("Write### HashCode"+ str(block_hash))

        else:   #when block is "old"
            hash_code = self.col_fam.get(path, columns=[str(nbBlock)])[str(nbBlock)]
            tmp = self.col_fam.get(hash_code, columns = ['content'])['content']
            block_hash = mmh3.hash64(tmp+data[:rest])
            self.col_fam.insert(path, {str(nbBlock): str(block_hash)})
            self.col_fam.insert(str(block_hash), {"content": tmp+data[:rest]})
            #print("Write### HashCode"+ str(block_hash))
            i = 0
            while(i < nbNewBlocks):
                content = data[(rest+i*sizeBlock):(rest+(i+1)*sizeBlock)]
                block_hash = mmh3.hash64(content) 
                self.col_fam.insert(path, {str(i+nbBlock+1): str(block_hash)})

                #content = data[(i*sizeBlock):((i+1)*sizeBlock)]
                print("######### " +str(i+1) +" submit begin!!!")
                futures.append(pool.submit(write_multi, block_hash, content))
                print("######### " +str(i+1) +" submit end!!!")
                i = i+1
            #wait(futures)
            if(lenData > rest + nbNewBlocks*sizeBlock):
                block_hash = mmh3.hash64(data[(rest+nbNewBlocks*sizeBlock):])
                self.col_fam.insert(path, {str(nbNewBlocks+nbBlock+1): str(block_hash)})
                self.col_fam.insert(str(block_hash), {"content": data[(rest+nbNewBlocks*sizeBlock):]})
                #print("Write### HashCode"+ str(block_hash))
                
        end = time()
        print("************* Time: " + str(end-start))
        #cassandra
        #self.col_fam.insert(path, {"content": self.data[path]})
        self.col_fam.insert("files", {"metadata": json.dumps(self.files)})
        wait(futures)
        m = ""
        for future in as_completed(futures):
            try:
                print("#### result " +future.result())
            except Exception as exc:
                print("exception ......."+ str(exc))

        #print(str(donnee))
        return len(data)


if __name__ == '__main__':
    if len(argv) != 2:
        print('usage: %s <mountpoint>' % argv[0])
        exit(1)

    #logging.basicConfig(level=logging.DEBUG)
    fuse = FUSE(Cassandra(), argv[1], foreground=True)