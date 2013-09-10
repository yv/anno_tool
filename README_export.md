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
python annodb2exml.py release.export RELEASE

python annodb2export.py release.export RELEASE

e.g.
python annodb2export.py /home/obxvy01/r8final.export R8FINAL
