:: build-bin-pkgs.bat
::
:: Uses the R installation located in
::   E:\biocbld\bbs-2.0-bioc\R\bin\R
:: to build binary packages from the source packages located in
::   E:\biocbld\bbs-2.0-data-annotation\src-pkgs
:: The resulting packages are stored in
::   E:\biocbld\bbs-2.0-data-annotation\bin-pkgs
::
:: Questions/help: hpages@fhcrc.org (ext. 5791)
:: Last modified: 2006-12-16

CD bin-pkgs
DEL /Q *

FOR %%a IN (..\src-pkgs\*.tar.gz) DO E:\biocbld\bbs-2.0-bioc\R\bin\R CMD INSTALL --build --library=..\Rlib %%a

CD ..
