#!/usr/bin/env python3
from peaclock import __version__
import setuptools
import argparse
import os.path
import snakemake
import sys
from tempfile import gettempdir
import tempfile
import pprint
import json
import csv
import os
from datetime import datetime
from Bio import SeqIO

import pkg_resources
from . import _program

import peaclockfunks as qcfunk
import custom_logger as custom_logger
import log_handler_handle as lh

thisdir = os.path.abspath(os.path.dirname(__file__))
cwd = os.getcwd()

def main(sysargs = sys.argv[1:]):

    parser = argparse.ArgumentParser(prog = _program, 
    description='peaclock: Predicted Epigenetic Age Clock', 
    usage='''peaclock -i <path/to/reads> -b <path/to/data> [options]''')

    parser.add_argument('-i','--read-path',help="Input the path to the reads",dest="read_path")
    parser.add_argument('-c',"--configfile",help="Config file with PEAClock run settings",dest="configfile")
    parser.add_argument('-b','--barcodes-csv',help="CSV file describing which barcodes were used on which sample",dest="barcodes_csv")
    parser.add_argument('-k','--barcode-kit',help="Indicates which barcode kit was used. Default: native. Options: native, rapid, pcr, all",dest="barcode_kit")

    parser.add_argument('--demultiplex',action="store_true",help="Indicates that your reads have not been demultiplexed and will run guppy demultiplex on your provided read directory",dest="demultiplex")
    parser.add_argument('--path-to-guppy',action="store_true",help="Path to guppy_barcoder executable",dest="path_to_guppy")

    parser.add_argument('-s',"--species", action="store",help="Indicate which species is being sequenced", dest="species")
    parser.add_argument("-r","--report",action="store_true",help="Generate markdown report of estimated age")

    parser.add_argument('-o','--output-prefix', action="store",help="Output prefix. Default: peaclock_<species>_<date>")
    parser.add_argument('--outdir', action="store",help="Output directory. Default: current working directory")
    parser.add_argument('--tempdir',action="store",help="Specify where you want the temp stuff to go. Default: $TMPDIR")
    parser.add_argument("--no-temp",action="store_true",help="Output all intermediate files, for dev purposes.")
    
    parser.add_argument('-n', '--dry-run', action='store_true',help="Go through the motions but don't actually run")
    parser.add_argument('-t', '--threads', action='store',type=int,help="Number of threads")
    parser.add_argument("--verbose",action="store_true",help="Print lots of stuff to screen")
    parser.add_argument("-v","--version", action='version', version=f"peaclock {__version__}")

    """
    Exit with help menu if no args supplied
    """

    if len(sysargs)<1: 
        parser.print_help()
        sys.exit(-1)
    else:
        args = parser.parse_args(sysargs)
    
    """
    Initialising dicts
    """

    config = cfunk.get_defaults()

    configfile = qcfunk.look_for_config(args.configfile,cwd,config)

    # if a yaml file is detected, add everything in it to the config dict
    if configfile:
        qcfunk.parse_yaml_file(configfile, config)
    

    """
    Get outdir, tempdir and the data
    """
    # default output dir
    qcfunk.get_outdir(args.outdir,args.output_prefix,cwd,config)

    # specifying temp directory, outdir if no_temp (tempdir becomes working dir)
    tempdir = qcfunk.get_temp_dir(args.tempdir, args.no_temp,cwd,config)

    # get data for a particular species, and get species
    qcfunk.get_package_data(thisdir, args.species, config)

    # add min and max read lengths to the config
    qcfunk.get_read_length_filter(config)

    # looks for basecalled directory
    qcfunk.look_for_basecalled_reads(args.read_path,cwd,config)
    
    # looks for the csv file saying which barcodes in sample
    qcfunk.look_for_barcodes_csv(args.barcodes_csv,cwd,config)

    """
    Configure whether guppy barcoder needs to be run
    """

    look_for_guppy_barcoder(args.demultiplex,args.path_to_guppy,cwd,config)


    # don't run in quiet mode if verbose specified
    if args.verbose:
        quiet_mode = False
        config["log_string"] = ""
    else:
        quiet_mode = True
        lh_path = os.path.realpath(lh.__file__)
        config["log_string"] = f"--quiet --log-handler-script {lh_path} "

    qcfunk.add_arg_to_config("threads",args.threads,config)
    
    try:
        config["threads"]= int(config["threads"])
    except:
        sys.stderr.write(qcfunk.cyan('Error: Please specifiy an integer for variable `threads`.\n'))
        sys.exit(-1)
    threads = config["threads"]

    print(f"Number of threads: {threads}\n")

    # find the master Snakefile
    snakefile = qcfunk.get_snakefile(thisdir)

    if args.verbose:
        print("\n**** CONFIG ****")
        for k in sorted(config):
            print(qcfunk.green(k), config[k])

        status = snakemake.snakemake(snakefile, printshellcmds=True, forceall=True, force_incomplete=True,
                                        workdir=tempdir,config=config, cores=threads,lock=False
                                        )
    else:
        logger = custom_logger.Logger()
        status = snakemake.snakemake(snakefile, printshellcmds=False, forceall=True,force_incomplete=True,workdir=tempdir,
                                    config=config, cores=threads,lock=False,quiet=True,log_handler=logger.log_handler
                                    )

    if status: # translate "success" into shell exit code of 0
       return 0

    return 1

if __name__ == '__main__':
    main()