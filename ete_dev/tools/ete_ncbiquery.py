#!/usr/bin/env python 

import sys
import os
from argparse import ArgumentParser
from string import strip
import logging as log

from ete_dev import PhyloTree, NCBITaxa
from common import __CITATION__

# Loads database
MODULE_PATH = os.path.split(os.path.realpath(__file__))[0]


__DESCRIPTION__ = '''
#  - treedist -
# ===================================================================================
#  
# 'ncbiquery' is a tool tor querying a local copy of the NCBI taxonomy database for 
# taxid/name conversions, automatic tree annotation or retrieving parsed and pruned 
# NCBI taxonomy tree topologies in newick format. 
#
%s
#  
# ===================================================================================
'''% __CITATION__

log.basicConfig(level=log.INFO, \
                    format="%(levelname)s - %(message)s" )


def test():
    # TESTS
    ncbi.get_sp_lineage("9606")
    t = ncbi.get_topology([9913,31033,7955,9606,7719,9615,44689,10116,7227,9031,13616,7165,8364,99883,10090,9598])
    ncbi.annotate_tree(t)
    print t.get_ascii(show_internal=True, compact=False)
    t.show()

def main(argv):
    
    parser = ArgumentParser(description=__DESCRIPTION__)

    parser.add_argument("--db",  dest="dbfile",
                        type=str,
                        help="""NCBI sqlite3 db file.""")

    input_args = parser.add_argument_group('TAXID INPUT OPTIONS')
    
    input_args.add_argument("-i", "--taxid", dest="taxid", nargs="+",  
                        type=int, 
                        help="""taxids (space separated)""")

    input_args.add_argument("-if", "--taxid_file", dest="taxid_file",   
                        type=str, 
                        help="""file containing a list of taxids (one per line)""")

    input_args.add_argument("-t", "--reftree", dest="reftree",   
                        type=str, 
                        help="""Read taxids from the provided tree.""")
    
    input_args.add_argument("--reftree_attr", dest="reftree_attr",   
                        type=str, default="name",
                        help="""tree attribute encoding for taxid numbers.""")

    name_input_args = parser.add_argument_group('NAME INPUT OPTIONS')
    
    name_input_args.add_argument("-n", "--name", dest="names", nargs="+",  
                        type=str, 
                        help="""species or taxa names (comma separated)""")

    name_input_args.add_argument("-nf", "--names_file", dest="names_file",   
                        type=str, 
                        help="""file containing a list of taxids (one per line)""")
    name_input_args.add_argument("--fuzzy", dest="fuzzy", type=float,
                        help=("Tries a fuzzy (and SLOW) search for those"
                              " species names that could not be translated"
                              " into taxids. A float number must be provided"
                              " indicating the minimum string similarity."))

    output_args = parser.add_argument_group('OUTPUT OPTIONS')
    
    output_args.add_argument("-x", "--taxonomy", dest="taxonomy",   
                        type=str, 
                        help=("dump a pruned version of the NCBI taxonomy"
                              " tree containing target species into the specified file"))

    output_args.add_argument("-l", "--list", dest="info_list",   
                        type=str, 
                        help="""dump NCBI taxonmy information for each target species into the specified file. """)

    output_args.add_argument("-a", "--annotated", dest="annotated_tree",   
                        type=str, 
                        help="dump the annotated tree of the input reftree provided with -t into the specified file.")                             
    
    output_args.add_argument("--collapse_subspecies", dest="collapse_subspecies",   
                        action="store_true",
                        help=("When used, all nodes under the the species rank"
                              " are collapsed, so all species and subspecies"
                              " are seen as sister nodes"))

    output_args.add_argument("--rank_limit", dest="rank_limit",   
                        type=str,
                        help=("When used, all nodes under the provided rank"
                              " are discarded"))
    
    output_args.add_argument("--full_lineage", dest="full_lineage",   
                        action="store_true",
                        help=("When used, topology is not pruned to avoid "
                              " one-child-nodes, so the complete lineage"
                              " track leading from root to tips is kept."))
        
    args = parser.parse_args(argv)

    taxid_source = args.taxid or args.taxid_file or args.reftree
    name_source = args.names or args.names_file
    if not taxid_source and not name_source:
        parser.error('At least one input source is required')
    if taxid_source and name_source:
        parser.error('taxid and name options are mutually exclusive')
        
    if not args.taxonomy and not args.info_list and not args.annotated_tree:
        parser.error('At least one output option is required')
        
    
    ncbi = NCBITaxa(args.dbfile)
        
    all_names = set([])
    all_taxids = []

    if args.names_file:
        all_names.update(map(strip, open(args.names_file, "rU").read().split("\n")))
        
    if args.names:
        all_names.update(map(strip, " ".join(args.names).split(",")))
        
    all_names.discard("")
    #all_names = set([n.lower() for n in all_names])
    not_found = set()
    name2realname = {}
    name2score = {}
    if all_names:
        log.info("Dumping name translations in %s.name_translation.txt ... ")
        name2id = ncbi.get_name_translator(all_names)
        not_found = all_names - set(name2id.keys())

        if args.fuzzy and not_found:
            log.info("%s unknown names", len(not_found))
            for name in not_found:
                # enable extension loading
                tax, realname, sim = ncbi.get_fuzzy_name_translation(name, args.fuzzy)
                if tax:
                    name2id[name] = tax
                    name2realname[name] = realname
                    name2score[name] = "Fuzzy:%0.2f" %sim
                    
        for name in all_names:
            taxid = name2id.get(name, "???")
            realname = name2realname.get(name, name)
            score = name2score.get(name, "Exact:1.0")
            print "\t".join(map(str, [score, name, realname.capitalize(), taxid]))
            
    if args.taxid_file:
        all_taxids.extend(map(strip, open(args.taxid_file, "rU").read().split("\n")))
    if args.taxid:
        all_taxids.extend(args.taxid)
        
    reftree = None
    if args.reftree:
        reftree = PhyloTree(args.reftree)
        all_taxids.extend(list(set([getattr(n, args.reftree_attr) for n in reftree.iter_leaves()])))
       
    if all_taxids and args.info_list:
        all_taxids = set(all_taxids)
        all_taxids.discard("")
        all_taxids, merge_conversion = ncbi._translate_merged(all_taxids)
        outfile = args.info_list+".info.txt"
        log.info("Dumping %d taxid translations in %s ..." %(len(all_taxids), outfile))
        all_taxids.discard("")
        translator = ncbi.get_taxid_translator(all_taxids)
        OUT = open(outfile, "w")
        for taxid, name in translator.iteritems():
            lineage = ncbi.get_sp_lineage(taxid)
            named_lineage = ','.join(ncbi.translate_to_names(lineage))
            lineage = ','.join(map(str, lineage))
            print >>OUT, "\t".join(map(str, [merge_conversion.get(int(taxid), taxid), name, named_lineage, lineage ]))
            
        OUT.close()    
        for notfound in set(map(str, all_taxids)) - set(str(k) for k in translator.iterkeys()):
            print >>sys.stderr, notfound, "NOT FOUND"
    
    if all_taxids and args.taxonomy:
        all_taxids = set(all_taxids)
        all_taxids.discard("")
        log.info("Dumping NCBI taxonomy of %d taxa in %s.*.nw ..." %(len(all_taxids), args.taxonomy))

        t = ncbi.get_topology(all_taxids, args.full_lineage, args.rank_limit)
        
        id2name = ncbi.get_taxid_translator([n.name for n in t.traverse()])
        for n in t.traverse():
            n.add_features(taxid=n.name)
            n.add_features(sci_name=str(id2name.get(int(n.name), "?")))
            n.name = "%s{%s}" %(id2name.get(int(n.name), n.name), n.name)
            lineage = ncbi.get_sp_lineage(n.taxid)
            n.add_features(named_lineage = '|'.join(ncbi.translate_to_names(lineage)))
            
        if args.collapse_subspecies:
            species_nodes = [n for n in t.traverse() if n.rank == "species"
                             if int(n.taxid) in all_taxids]
            for sp_node in species_nodes:
                bellow = sp_node.get_descendants()
                if bellow:
                    # creates a copy of the species node
                    connector = sp_node.__class__()
                    for f in sp_node.features:
                        connector.add_feature(f, getattr(sp_node, f))
                    connector.name = connector.name + "{species}"
                    for n in bellow:
                        n.detach()
                        n.name = n.name + "{%s}" %n.rank
                        sp_node.add_child(n)
                    sp_node.add_child(connector)
                    sp_node.add_feature("collapse_subspecies", "1")
                
            
        t.write(format=9, outfile=args.taxonomy+".names.nw")
        t.write(format=8, outfile=args.taxonomy+".allnames.nw")
        t.write(format=9, features=["taxid", "name", "rank", "bgcolor", "sci_name", "collapse_subspecies", "named_lineage"],
                outfile=args.taxonomy+".full_annotation.nw")
        
        for i in t.iter_leaves():
            i.name = i.taxid
        t.write(format=9, outfile=args.taxonomy+".taxids.nw")
        t.write(format=8, outfile=args.taxonomy+".alltaxids.nw")


    if all_taxids and reftree:
        translator = ncbi.get_taxid_translator(all_taxids)
        for n in reftree.iter_leaves():
            if not hasattr(n, "taxid"):
                n.add_features(taxid=int(getattr(n, args.reftree_attr)))
            n.add_features(sci_name = translator.get(int(n.taxid), n.name))
            lineage = ncbi.get_sp_lineage(n.taxid)
            named_lineage = '|'.join(ncbi._translate_to_names(lineage))
            n.add_features(ncbi_track=named_lineage)
            
        print reftree.write(features=["taxid", "sci_name", "ncbi_track"])
  
if __name__ == '__main__':
    main(sys.argv[1:])
