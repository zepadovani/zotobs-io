@echo off
rem Atalho do zotobs para Windows (NAO TESTADO): zotobs <subcomando> ...
rem libraries/collections/search/show/collection -> biblioteca; o resto -> anotacoes.
rem (Opcoes globais como --zotero-dir devem vir DEPOIS do subcomando neste atalho.)
set "ZSCRIPT=%~dp0..\skills\zotero-anotacoes\scripts\zotero_anot.py"
for %%C in (libraries collections search show collection) do if /i "%~1"=="%%C" set "ZSCRIPT=%~dp0..\skills\zotero-biblioteca\scripts\zotero_lib.py"
uv run --script "%ZSCRIPT%" %*
