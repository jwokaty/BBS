#!/bin/bash
# ===================
# Settings for lconway
# ===================



#set -x  # print commands and their arguments as they are executed

export BBS_DEBUG="0"

export BBS_NODE_HOSTNAME="lconway"
export BBS_USER="biocbuild"
export BBS_WORK_TOPDIR="/Users/biocbuild/bbs-3.16-bioc"
export BBS_R_HOME="/Library/Frameworks/R.framework/Resources"
export BBS_NB_CPU=20        # 24 cores are available
export BBS_BUILD_CPU=15     # 24 cores are available
export BBS_CHECK_NB_CPU=18  # 24 cores are available

# Central build node is nebbiolo2 at DFCI.
export BBS_CENTRAL_RHOST="nebbiolo2"
export BBS_RSH_CMD="ssh -F /Users/biocbuild/.ssh/config"
export BBS_CENTRAL_ROOT_URL="http://155.52.207.166"
export BBS_PRODUCT_TRANSMISSION_MODE="asynchronous"



# Shared settings (by all Unix nodes).

wd0=$(pwd)
cd ..
. ./config.sh
cd "$wd0"
