#!/bin/bash
# =====================================================================
# Settings shared by all the Unix nodes involved in the 2.3-bioc builds
# =====================================================================


export BBS_MODE="bioc"

export BBS_BIOC_MANIFEST_FILE="bioc_2.3.manifest"

# What type of meat? Only 2 types are supported:
#   1: svn repo (contains pkg dirs)
#   2: CRAN-style local repo containing .tar.gz pkgs
export BBS_MEAT0_TYPE=1

# Where is it?
export BBS_MEAT0_RHOST="wilson2"
export BBS_MEAT0_RUSER="biocbuild"
export BBS_MEAT0_RDIR="/home/biocbuild/bbs-2.3-bioc/MEAT0"

# Triggers a MEAT0 update at beginning of prerun (stage1)
export BBS_UPDATE_MEAT0=1

# Local meat copy
export BBS_MEAT_PATH="$BBS_WORK_TOPDIR/meat"


wd1=`pwd`
cd ..
. ./config.sh
cd "$wd1"
