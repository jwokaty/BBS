@rem ===================
@rem Settings for tokay2
@rem ===================


set BBS_DEBUG=0

set BBS_NODE_HOSTNAME=tokay2
set BBS_USER=biocbuild
set BBS_WORK_TOPDIR=C:\Users\biocbuild\bbs-3.13-bioc
set BBS_R_HOME=%BBS_WORK_TOPDIR%\R
set BBS_NB_CPU=16
set BBS_CHECK_NB_CPU=26

set BBS_STAGE2_MODE=multiarch
set BBS_STAGE4_MODE=multiarch
set BBS_STAGE5_MODE=multiarch

@rem Central build node is nebbiolo1 at DFCI (ssh connections must be made via
@rem jump host ada.dfci.harvard.edu, see BBS_RSH_CMD below).
set BBS_CENTRAL_RHOST=155.52.47.135

@rem When used with StrictHostKeyChecking=no, ssh will automatically add new
@rem host keys to the user known hosts files (so it doesn't get stalled waiting
@rem for an answer when not run interactively).
set BBS_RSH_CMD=C:\cygwin\bin\ssh.exe -qi C:\Users\biocbuild\.BBS\id_rsa -o UserKnownHostsFile=C:\Users\biocbuild\.BBS\known_hosts -o StrictHostKeyChecking=no -J biocbuild@ada.dfci.harvard.edu



@rem Shared settings (by all Windows nodes)

set wd0=%cd%
cd ..
call config.bat
cd %wd0%
