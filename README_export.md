Exporting annotations
=====================

If you use anno_tool for the annotation of word senses or for the annotation of
discourse connectives, the annodb2export.py and annodb2exml.py tools allow the
export of annotation into either Negra Export (annodb2export) or ExportXMLv2
(annodb2exml). The latter needs a working installation of the PyTree library
and its exml module.

Both for annodb2exml and annodb2export, you will need the Negra Export file
that corresponds to the annotation database you want to export.

Usage:
python annodb2exml.py RELEASE release.export

python annodb2export.py RELEASE release.export

e.g.
~/anno_tool_env/bin/python annodb2export.py R8FINAL /home/obxvy01/r8final.export

(using the anno_tool_env - either by sourcing its activate script or by using the
Python alias in its directory - allows the programs to use the PyTree library,
which is installed in anno_tool_env instead of globally).

Moving annotations from one release to another
==============================================

If you have created an annotation database for a new version of the treebank
(by creating a CQP corpus from the output of export2cqp, adding it to CQP's
registry and the pycwb.corpora.nologin list in config.yml), you still need
to transfer the annotations from the old corpus version. This can be achieved
using

python transfer_discourse.py RELEASE_OLD RELEASE_NEW
python transfer_tasks.py RELEASE_OLD RELEASE_NEW
