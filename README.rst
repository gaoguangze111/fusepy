I Introduction

I.1 Context

Inspired from GoogleFS, under the guidance of Télécom SudParis’s professor, we developed this decentralised distributed file system. As a part of the curriculum in Télécom SudParis, this project is our final-year project. 

I.2 State of the art

In computing, a distributed file system is a file system that allows users to access files from multiple hosts. This makes it possible for different users on multiple machines to share files and storage resources. Until now, many types of distributed file systems have been developed, such as Sun Microsystems’ Network File System (NFS), Google File System (GFS) and Hadoop Distributed File System. Some of these distributed file systems such as NFA use a client/server architecture which let users view, store and update files using a remote server. This kind of centralized architecture has been used for over ten years and there is no doubt that this technology greatly facilitate sharing files for users and managing data for administrator but there are also some disadvantages such as the high price of a host, poor security and low scalability. 

Recent years, decentralized distributed file systems such as GoogleFS have appeared and these systems make up these deficiencies. Instead of using a centralized architecture with a host, these distributed file system use a cluster who consists of multiple nodes. These nodes are divided into two types : some master nodes and a large number of normal nodes. Each node is a computer that is much more cheaper than a high performance so firstly decentralized distributed file system is much more cheaper than a centralized file system. Secondly, when we store a file in a decentralized file system we can configure the replication factor for our files. Besides, these systems are fault-tolerant. Some of these nodes’ breakdowns would not lead to the stop of the total system. So decentralized file system is safer than centralized file system. Thirdly, we can easily add new machines to the cluster so decentralized file system also provide a better scalability.

I.3 Problematic

To realize a file system, the most important problem is to resolve the storage problem. Recent years, the prosperity of big data greatly promote the development of no-sql databases. Apache Cassandra is a free and open-source distributed database management system designed to handle large amounts of data, providing high security and high scalability. Besides Cassandra achieves a high throughput with a large number of nodes and it’s reputed for its performance among those no-sql databases. Another problem of the project is to customize a file system. The open-source project Filesystem in Userspace (FUSE) provides us a robust solution, which allow us to create a file system in userspace. Furthermore, among programming languages, Python is highly efficient for project development and cross-platform so Python is one of our project’s best choix.

I.4 Overview of the solutions

In this project, we use cassandra as our storage system and FUSE to customize a filesystem on Linux. Besides, we use Python as our programming language. Globally, the project is divided into three steps. In the first step we realize a simple version to get familiar with these systems. In this version, a file is stored in a row of Cassandra and a file’s data is stored in one column of the row. In the second step we divided a file’s data into multiple data blocks and save them in different columns. In the third step we introduce a structure like “inode” and parallelize read/write operation to optimize the performance.

II Solution design

II.1 Cassandra data model

The Cassandra data model is composed of several important elements :

●	Row and column : Rows and columns are the basic elements in cassandra. Each row consists of several columns. The difference with relational database is that we can define different columns for every row.

●	Table : Rows are organized into tables which is a distributed multi dimensional map indexed by a key.

●	Column family : Columns are grouped together into sets called column families. Cassandra has two kinds of columns families, simple and super column families. Super column families can be visualized as a column family whose elements are some column family.

II.2 FUSE Python module

FUSE (Filesystem in Userspace) is an interface for userspace programs to customize a file system in userspace without editing kernel code. This is achieved by running file system code in user space and FUSE provides a “bridge” to the actual kernel interfaces. Fusepy is a python module that provides a simple interface to FUSE

II.3 Solution detail

II.3.a First solution

In the first step we realised a naive solution without digging into the performance of the filesystem. The first version of file system is a one-level directory file system. In solution 1, we store all the metadata of file system in the first row of table. The row key is “files” and the content of this row is a dictionary of Python that saves every file’s metadata. Files’ metadata in the dictionary is referenced by the path of file in the filesystem. From the second row, each row store a file. We stored all the data of a file in just one column.

II.3.b Second solution (Split the file into blocks)

The first solution has a poor performance in our write experiente. Because every time when we change the file’s content we need to re-write all data. To solve this problem, we decide to split a file into data blocks and store these blocks in different columns. In this way we don’t need to re-write a file’s all data when we update the file.

The structure of second solution is presented below :

●	The first row still store all files’ metadata

●	From the second row, each row store one file

●	Instead of using only one column, we divide a file’s data into many blocks and store them in different columns.

	 	 	
The second solution has a much more better write performance than the first solution. For instance, to write a 6MB in our file system for solution 1 we need 89.34s. But for solution 2 we just need 6.92s. Besides the write execution time solution 2 increase more slowly than solution 1.

But the second solution also has insufficiency. We think that we could continue to augment our filesystem’s performance. 

III.3.c Third solution

In the second step, we divide data into blocks and store them in one row of cassandra. This mechanism allow us to store data in different blocks. But this mechanism also has two shortcomings.

-	Data blocks can’t be reused 

-	Limit for optimisation

So we need to find a solution to make it better. To overcome them, we introduced a  new structure in solution 3. The structure is Inode-like (file system in Linux), which allows us to reuse data blocks and to optimize read/write operations. The details of the structure and algorithms are presented below. 

Structure:

We consider a mechanism like “inode” in linux file system. 

-	A file has two parts: a file node and some data blocks. 

-	Every data block is stored in one separated rows. Every data block’s row has a key generated from this data block.

-	A file’s nodes only stores data blocks’ keys. 


Intuitively, every file’s data is divided into data blocks. We store these blocks in different rows. A file node just store “pointers” of data blocks. One data block can be shared by different files containing this “pointer”. Here, the “pointer” is the key of data block. 

Another challenge is how to generate data block key. One way is using hash function to generate hash code from content of data block. In fact, this project uses this solution (hash-based). 64 digits are used to save hashcode. So in theory, we can store 2^64 data blocks. However, another problem occurs. Hash codes have the risk of conflicts. How can we avoid conflicts? In our experiment, conflicts have very little possibility. So to simplify our solution, we choose to ignore them. But this is one important thing we need to deal with in the follow-up work.

Algorithms: 

After we have changed the structure to to Inode-like. We consider to ameliorate algorithms of read/write. We can see that data blocks are stored in different rows in cassandra nodes,  which make it possible to parallelize read/write operations. Intuitively,  that’s to say writing a file with several parallel processes at the same time and reading a file from different data blocks with different processes at the same time.

For a write operation:

1.	Process P0 divides data into different data blocks. Then P0 generates a key for every data block and sends <key, data block> to other free processes. 

2.	When getting a pair <key, data block>, a process write them to the cassandra cluster. Different processes execute tasks in parallel. 

3.	A process send back a ACK to P0 when finishing writing.

4.	P0 gets all ACK and returns a result. 


For a read operation:

1.	Process P0 gets the file node, reads data block keys. Then P0 sends data block keys to other free processes.

2.	When getting a data block key, a process reads the data block from the cassandra cluster. Different processes execute tasks in parallel. 

3.	A process sends the data block to P0 when finishing reading.

4.	P0 collects all returned data blocks and combines them into a result. 



IV Implementation and experiment

IV.1 Implementation 

Based on ideas above, we implement our system. Here, I’ll introduce the details of implementation. 


1. Programming language

This project uses python as programming language. Because we can use many useful functions and libraries for file system. And the scale of code is smaller.
 
2. Distributed storage

To store distributed data, we construct a cassandra cluster. Yous can find the tutorial of configuration of cassandra cluster in the website of cassandra. 

3. Customize the file system:

FUSE is a useful tool to customize a filesystem, which allows us create a file system without kernel programming. For this project, we use a FUSE interface of Python called fusepy. Using fusepy, we can construct this filesystem in userspace.

4. Parallelism 

Python has a package called “future”, which allow us to realize parallelism conveniently. Parallelism includes two types: multi threads and multi processes. Here we use multiple processes. 

IV.2 Performance

Globally, we realise three versions in three steps :

-	Naive solution

-	Divide data into data blocks

-	Inode-like structure and parallelism

To get a comparison. We test all these solutions in a cassandra cluster of 4 nodes. Replica factor is 2. In the environment of Linux, we use “time” and “dd” to test time latency of read/write operation. 

1. Naive solution

In the naive solution, the performance is acceptable when a file is very small. But along with increase of data, latency time explodes. For instance, writing a 2 M file needs 9.46s. When the size is 10 M, it needs 327.89s! 

The reason is that we store all file data into one block. Writing a file maybe needs many write operations. For every write operation, it needs read all previous data, add new data into it, and rewrite updated data. 

2. Divide data into data blocks

In this step, the performance is more linear. For instance, writing a 2 M file needs 2.34s, 4M needs 3.33s, and 10 M needs 9.85s. 
Because we divide data into data blocks. And latency time is more linear along with the increase of data. 

3. Inode)like structure and parallelism

In the third step’s experiment, we compare it to the second solution. We find that when a file is relatively small, solution 2 has a better performance. However, along with the increase of data, solution 3 has bigger and bigger advantage. For instance, 

2M	2.34s	2.42s

4M	3.31s	4.53s

6M	6.91s	5.36s


When analyse this result, the reason is that inode-like structure and parallelism are used. I-node like structure and parallelism need additional overhead compared with solution 2. When a file is relatively small, the overhead affects the performance. But along with the increase of data, the advantage of parallelism and reusability is more and more obvious. This explains the result. 


V Conclusion

The project's object is to implement a distributed file system. We work on three main aspects:

-	Deploy a cluster to store distributed data

-	Construct a prototype of distributed system

-	Test solutions and analyse performance

In detail,  we us cassandra, fusepy and python to implement this project. This prototype a  one-level directory file system. We realize the basic read/write operation. 

This prototype is relatively rough and need to be improved. To continue this project, we plan to:

-	Complete the structure of file system (ex. multi-level directory ).

-	Implement other operations

-	Solve conflicts of hash code

