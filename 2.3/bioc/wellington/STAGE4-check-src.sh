#!/bin/bash

. ./config.sh

. $BBS_HOME/utils/start-virtual-X.sh
$BBS_HOME/BBS-run.py STAGE4
. $BBS_HOME/utils/stop-virtual-X.sh
