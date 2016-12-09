#!/bin/env python
"""storus

Usage:
  storus.py [-ha] [--smilesCol=] [--nameCol=] smiles_file storage_dir 

Options:
  -h has header line
  -a append desctriptors to storage (see note below)
  --smilesCol column index (starting at 0) or header name for the smiles column
  --nameCol   column index (starting at 0) or header name for the name column

  smiles_file
  storage_dir

  If appending descriptors to a storage, the header, smiles and name columns
   must match the current storage.
"""
from __future__ import print_function
from descriptastorus.descriptors import rdDescriptors
from rdkit.Chem import AllChem

import sys
from rdkit import rdBase
rdBase.DisableLog("rdApp.*")

props = rdDescriptors.RDKitMorgan3CountsAndDescriptors()

def process( job ):
    res = []
    for index,smiles in job:
        counts = props.process(smiles)
        if not counts:
            continue
        res.append((index,counts))

    return res

def processInchi( job ):
    res = []
    for index,smiles in job:
        try:
            m = AllChem.MolFromSmiles(smiles)
        except:
            continue
        if not m:
            continue
        
        counts = props.processMol(m, smiles)
        inchi = AllChem.MolToInchi(m)
        key = AllChem.InchiToInchiKey(inchi)

        if not counts:
            continue
        res.append((index,counts,inchi,key))

    return res



if __name__ == "__main__":

    import argparse, os, shutil
    from descriptastorus import MolFileIndex, raw
    try:
        import kyotocabinet
    except:
        kyotocabinet = None
        
    parser = argparse.ArgumentParser()
    parser.add_argument("smilesfile",
                        help="file containing smiles strings")
    parser.add_argument("storage",
                        help="directory in which to store the descriptors")

    parser.add_argument("--hasHeader", action="store_true",
                        help="Indicate whether the smiles file has a header row")

    parser.add_argument("--index-inchikey", action="store_true",
                        help="Optionally index the descriptors with inchi keys")

    #parser.add_argument("--index-smiles", action="store_true",
    #                    help="Indicate whether the smiles file has a header column")
    
    parser.add_argument("--smilesColumn", default=0,
                        help="Row index (or header name if the file has a header) for the smiles column")
    parser.add_argument("--nameColumn", default=-1,
                        help="Row index (or header name if the file has a header) for the name column")
    
    parser.add_argument("--seperator", default="\t",
                        help="Row index (or header name if the file has a header) for the name column")
    

    args = parser.parse_args()
    print (args)

    inchiKey = args.index_inchikey
    if inchiKey and not kyotocabinet:
        print("Indexing inchikeys requires kyotocabinet, please install kyotocabinet",
              file=sys.stderr)
        sys.exit(1)
    
    # make the storage directory
    if os.path.exists(args.storage):
        raise IOError("Directory for descriptastorus already exists: %s"%args.storage)
    
    os.mkdir(args.storage)
    # index the molfile
    indexdir = os.path.join(args.storage, "__molindex__")

    sm = MolFileIndex.MakeSmilesIndex(args.smilesfile, indexdir,
                                      sep=args.seperator,
                                      hasHeader = args.hasHeader,
                                      smilesColumn = args.smilesColumn,
                                      nameColumn = args.nameColumn)
    print("Creating descriptors for %s molecules..."%sm.N)

                                      
    import multiprocessing
    import time, os, sys, numpy
        
    numstructs = sm.N
    s = raw.MakeStore(props.GetColumns(), sm.N, args.storage, checkDirectoryExists=False)
    if args.index_inchikey:
        cabinet = kyotocabinet.DB()
        inchi = os.path.join(args.storage, "inchikey.kch")
        cabinet.open(inchi, kyotocabinet.DB.OWRITER | kyotocabinet.DB.OCREATE)

    if args.nameColumn != -1:
        name_cabinet = kyotocabinet.DB()
        name = os.path.join(args.storage, "name.kch")
        name_cabinet.open(name, kyotocabinet.DB.OWRITER | kyotocabinet.DB.OCREATE)
        
        
    num_cpus = multiprocessing.cpu_count()
    pool = multiprocessing.Pool(num_cpus)
    print ("Number of molecules to process", numstructs)
    
    done = False
    count = 0
    batchsize = 10000
    badColumnWarning = False
    inchies = {}
    while 1:
        lastcount = count
        joblist = []
        for cpuidx in range(num_cpus):
            jobs = []
            for i in range(count, min(count+batchsize, sm.N)):
                jobs.append((i,sm.getMol(i)))
            count = i+1
            if jobs:
                joblist.append(jobs)
        if not joblist:
            break
        
        if args.index_inchikey:
            results = pool.map(processInchi, joblist)
        else:
            results = pool.map(process, joblist)
            

        for result in results:
            if not badColumnWarning and len(result) == 0:
                badColumnWarning = True
                print("WARNING: no molecules processed in batch, check the smilesColumn",
                      file=sys.stderr)
                print("WARNING: First 10 smiles:\n",
                      file=sys.stderr)
                print("\n".join([sm.getMol(i) for i in range(0, min(sm.N,10))]),
                      file=sys.stderr)

            if args.index_inchikey:
                for i,v,inchi,key in result:
                    s.putRow(i, v)
                    if inchi in inchies:
                        inchies[key].append(i)
                    else:
                        inchies[key] = [i]

                    if args.nameColumn != -1:
                        name = sm.getName(i)
                        name_cabinet[name] = i
                
            else:
                for i,v in result:
                    s.putRow(i, v)
                    name = sm.getName(i)
                    if name in name_cabinet:
                        print("WARNING: name %s duplicated at molecule %d and %d"%(
                            name, name_cabinet[name], i))
                    else:
                        name_cabinet[name] = i
                
        print("Done with %s out of %s"%(count, sm.N), file=sys.stderr)

    if args.index_inchikey:
        print("Indexing inchies", file=sys.stderr)
        for k in sorted(inchies):
            cabinet[k] = repr(inchies[k])
    

        
            
            
