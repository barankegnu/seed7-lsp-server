# rf10_probe.sh -- DRIVER (analysis.sd7 driverFor) vs LEAD (buffer text), one row per route
# columns: route file verdict errors=<errorCount> records=<length(globalObjects)> string=<records with file()=STRING> first=<getError(1).message>
# seed7 tree: /home/username/seed7 c93282a6
DRIVER /home/username/seed7/lib/aes_gcm.s7i CLEAN errors=0 records=5989 string=0 first=
LEAD /home/username/seed7/lib/aes_gcm.s7i CLEAN errors=0 records=5989 string=19 first=
DRIVER /home/username/seed7/lib/aes.s7i CLEAN errors=0 records=5437 string=0 first=
LEAD /home/username/seed7/lib/aes.s7i CLEAN errors=0 records=5437 string=16 first=
DRIVER /home/username/seed7/lib/arc4.s7i CLEAN errors=0 records=4151 string=0 first=
LEAD /home/username/seed7/lib/arc4.s7i CLEAN errors=0 records=4151 string=7 first=
DRIVER /home/username/seed7/lib/archive_base.s7i CLEAN errors=0 records=3410 string=0 first=
LEAD /home/username/seed7/lib/archive_base.s7i CLEAN errors=0 records=3410 string=4 first=
DRIVER /home/username/seed7/lib/archive.s7i CLEAN errors=0 records=19865 string=0 first=
LEAD /home/username/seed7/lib/archive.s7i CLEAN errors=0 records=19865 string=3 first=
DRIVER /home/username/seed7/lib/array.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/array.s7i NOISY errors=16 records=3060 string=0 first=Redeclaration of "ARRAY_IDX_RANGE"
DRIVER /home/username/seed7/lib/ar.s7i CLEAN errors=0 records=5929 string=0 first=
LEAD /home/username/seed7/lib/ar.s7i CLEAN errors=0 records=5929 string=53 first=
DRIVER /home/username/seed7/lib/asn1oid.s7i CLEAN errors=0 records=5069 string=0 first=
LEAD /home/username/seed7/lib/asn1oid.s7i CLEAN errors=0 records=5069 string=62 first=
DRIVER /home/username/seed7/lib/asn1.s7i CLEAN errors=0 records=4963 string=0 first=
LEAD /home/username/seed7/lib/asn1.s7i CLEAN errors=0 records=4963 string=59 first=
DRIVER /home/username/seed7/lib/basearray.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/basearray.s7i NOISY errors=2 records=3060 string=0 first=Redeclaration of "array [ (val integer: minIdx) .. ] (val type: baseType)"
DRIVER /home/username/seed7/lib/bigfile.s7i CLEAN errors=0 records=3484 string=0 first=
LEAD /home/username/seed7/lib/bigfile.s7i CLEAN errors=0 records=3484 string=12 first=
DRIVER /home/username/seed7/lib/bigint.s7i CLEAN errors=0 records=3472 string=0 first=
LEAD /home/username/seed7/lib/bigint.s7i CLEAN errors=0 records=3472 string=66 first=
DRIVER /home/username/seed7/lib/bigrat.s7i CLEAN errors=0 records=4053 string=0 first=
LEAD /home/username/seed7/lib/bigrat.s7i CLEAN errors=0 records=4053 string=44 first=
DRIVER /home/username/seed7/lib/bin16.s7i CLEAN errors=0 records=4421 string=0 first=
LEAD /home/username/seed7/lib/bin16.s7i CLEAN errors=0 records=4421 string=57 first=
DRIVER /home/username/seed7/lib/bin32.s7i CLEAN errors=0 records=3665 string=0 first=
LEAD /home/username/seed7/lib/bin32.s7i CLEAN errors=0 records=3665 string=44 first=
DRIVER /home/username/seed7/lib/bin64.s7i CLEAN errors=0 records=4081 string=0 first=
LEAD /home/username/seed7/lib/bin64.s7i CLEAN errors=0 records=4081 string=48 first=
DRIVER /home/username/seed7/lib/bitdata.s7i CLEAN errors=0 records=5246 string=0 first=
LEAD /home/username/seed7/lib/bitdata.s7i CLEAN errors=0 records=5246 string=52 first=
DRIVER /home/username/seed7/lib/bitmapfont.s7i CLEAN errors=0 records=6821 string=0 first=
LEAD /home/username/seed7/lib/bitmapfont.s7i CLEAN errors=0 records=6821 string=9 first=
DRIVER /home/username/seed7/lib/bitsetof.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/bitsetof.s7i NOISY errors=2 records=3060 string=0 first=Redeclaration of "bitset (val type: baseType)"
DRIVER /home/username/seed7/lib/bitset.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/bitset.s7i NOISY errors=106 records=3060 string=0 first=Redeclaration of "bitset"
DRIVER /home/username/seed7/lib/blowfish.s7i CLEAN errors=0 records=5428 string=0 first=
LEAD /home/username/seed7/lib/blowfish.s7i CLEAN errors=0 records=5428 string=11 first=
DRIVER /home/username/seed7/lib/bmp.s7i CLEAN errors=0 records=10562 string=0 first=
LEAD /home/username/seed7/lib/bmp.s7i CLEAN errors=0 records=10562 string=56 first=
DRIVER /home/username/seed7/lib/boolean.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/boolean.s7i NOISY errors=94 records=3060 string=0 first=Redeclaration of "boolean"
DRIVER /home/username/seed7/lib/browser.s7i CLEAN errors=0 records=15055 string=0 first=
LEAD /home/username/seed7/lib/browser.s7i CLEAN errors=0 records=15055 string=7 first=
DRIVER /home/username/seed7/lib/bstring.s7i CLEAN errors=0 records=3543 string=0 first=
LEAD /home/username/seed7/lib/bstring.s7i CLEAN errors=0 records=3543 string=22 first=
DRIVER /home/username/seed7/lib/bytedata.s7i CLEAN errors=0 records=4214 string=0 first=
LEAD /home/username/seed7/lib/bytedata.s7i CLEAN errors=0 records=4214 string=45 first=
DRIVER /home/username/seed7/lib/bzip2.s7i CLEAN errors=0 records=7507 string=0 first=
LEAD /home/username/seed7/lib/bzip2.s7i CLEAN errors=0 records=7507 string=54 first=
DRIVER /home/username/seed7/lib/cards.s7i CLEAN errors=0 records=6022 string=0 first=
LEAD /home/username/seed7/lib/cards.s7i CLEAN errors=0 records=6022 string=77 first=
DRIVER /home/username/seed7/lib/category.s7i CLEAN errors=0 records=3394 string=0 first=
LEAD /home/username/seed7/lib/category.s7i CLEAN errors=0 records=3394 string=66 first=
DRIVER /home/username/seed7/lib/cc_conf.s7i CLEAN errors=0 records=5209 string=0 first=
LEAD /home/username/seed7/lib/cc_conf.s7i CLEAN errors=0 records=5209 string=8 first=
DRIVER /home/username/seed7/lib/ccittfax.s7i CLEAN errors=0 records=7321 string=0 first=
LEAD /home/username/seed7/lib/ccittfax.s7i CLEAN errors=0 records=7321 string=59 first=
DRIVER /home/username/seed7/lib/cgidialog.s7i CLEAN errors=0 records=13165 string=0 first=
LEAD /home/username/seed7/lib/cgidialog.s7i CLEAN errors=0 records=13165 string=118 first=
DRIVER /home/username/seed7/lib/cgi.s7i CLEAN errors=0 records=4639 string=0 first=
LEAD /home/username/seed7/lib/cgi.s7i CLEAN errors=0 records=4639 string=2 first=
DRIVER /home/username/seed7/lib/char.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/char.s7i NOISY errors=74 records=3060 string=0 first=Redeclaration of "char"
DRIVER /home/username/seed7/lib/charsets.s7i CLEAN errors=0 records=3161 string=0 first=
LEAD /home/username/seed7/lib/charsets.s7i NOISY errors=7729 records=3161 string=87 first=Illegal character in text "\135;" (U+0087)
DRIVER /home/username/seed7/lib/chartype.s7i CLEAN errors=0 records=3097 string=0 first=
LEAD /home/username/seed7/lib/chartype.s7i CLEAN errors=0 records=3097 string=37 first=
DRIVER /home/username/seed7/lib/cipher.s7i CLEAN errors=0 records=3482 string=0 first=
LEAD /home/username/seed7/lib/cipher.s7i CLEAN errors=0 records=3482 string=23 first=
DRIVER /home/username/seed7/lib/clib_file.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/clib_file.s7i NOISY errors=64 records=3060 string=0 first=Redeclaration of "clib_file"
DRIVER /home/username/seed7/lib/cli_cmds.s7i CLEAN errors=0 records=5313 string=0 first=
LEAD /home/username/seed7/lib/cli_cmds.s7i CLEAN errors=0 records=5313 string=31 first=
DRIVER /home/username/seed7/lib/color.s7i CLEAN errors=0 records=3157 string=0 first=
LEAD /home/username/seed7/lib/color.s7i CLEAN errors=0 records=3157 string=49 first=
DRIVER /home/username/seed7/lib/complex.s7i CLEAN errors=0 records=3456 string=0 first=
LEAD /home/username/seed7/lib/complex.s7i CLEAN errors=0 records=3456 string=31 first=
DRIVER /home/username/seed7/lib/compress.s7i CLEAN errors=0 records=3064 string=0 first=
LEAD /home/username/seed7/lib/compress.s7i CLEAN errors=0 records=3064 string=4 first=
DRIVER /home/username/seed7/lib/console.s7i CLEAN errors=0 records=3289 string=0 first=
LEAD /home/username/seed7/lib/console.s7i CLEAN errors=0 records=3289 string=25 first=
DRIVER /home/username/seed7/lib/cpio.s7i CLEAN errors=0 records=6693 string=0 first=
LEAD /home/username/seed7/lib/cpio.s7i CLEAN errors=0 records=6693 string=53 first=
DRIVER /home/username/seed7/lib/crc32.s7i CLEAN errors=0 records=3772 string=0 first=
LEAD /home/username/seed7/lib/crc32.s7i CLEAN errors=0 records=3772 string=10 first=
DRIVER /home/username/seed7/lib/crc64.s7i CLEAN errors=0 records=4183 string=0 first=
LEAD /home/username/seed7/lib/crc64.s7i CLEAN errors=0 records=4183 string=5 first=
DRIVER /home/username/seed7/lib/cronos16.s7i CLEAN errors=0 records=6972 string=0 first=
LEAD /home/username/seed7/lib/cronos16.s7i NOISY errors=99 records=6972 string=2 first="'" expected found "\194;" (U+00c2)
DRIVER /home/username/seed7/lib/cronos27.s7i CLEAN errors=0 records=6972 string=0 first=
LEAD /home/username/seed7/lib/cronos27.s7i NOISY errors=99 records=6972 string=2 first="'" expected found "\194;" (U+00c2)
DRIVER /home/username/seed7/lib/csv.s7i CLEAN errors=0 records=3063 string=0 first=
LEAD /home/username/seed7/lib/csv.s7i CLEAN errors=0 records=3063 string=3 first=
DRIVER /home/username/seed7/lib/db_prop.s7i CLEAN errors=0 records=5211 string=0 first=
LEAD /home/username/seed7/lib/db_prop.s7i CLEAN errors=0 records=5211 string=47 first=
DRIVER /home/username/seed7/lib/deflate.s7i CLEAN errors=0 records=6555 string=0 first=
LEAD /home/username/seed7/lib/deflate.s7i CLEAN errors=0 records=6555 string=23 first=
DRIVER /home/username/seed7/lib/des.s7i CLEAN errors=0 records=5530 string=0 first=
LEAD /home/username/seed7/lib/des.s7i CLEAN errors=0 records=5530 string=14 first=
DRIVER /home/username/seed7/lib/dialog.s7i CLEAN errors=0 records=5793 string=0 first=
LEAD /home/username/seed7/lib/dialog.s7i CLEAN errors=0 records=5793 string=11 first=
DRIVER /home/username/seed7/lib/dir.s7i CLEAN errors=0 records=4294 string=0 first=
LEAD /home/username/seed7/lib/dir.s7i CLEAN errors=0 records=4294 string=8 first=
DRIVER /home/username/seed7/lib/draw.s7i CLEAN errors=0 records=5195 string=0 first=
LEAD /home/username/seed7/lib/draw.s7i CLEAN errors=0 records=5195 string=65 first=
DRIVER /home/username/seed7/lib/duration.s7i CLEAN errors=0 records=3342 string=0 first=
LEAD /home/username/seed7/lib/duration.s7i CLEAN errors=0 records=3342 string=50 first=
DRIVER /home/username/seed7/lib/echo.s7i CLEAN errors=0 records=3114 string=0 first=
LEAD /home/username/seed7/lib/echo.s7i CLEAN errors=0 records=3114 string=4 first=
DRIVER /home/username/seed7/lib/editline.s7i CLEAN errors=0 records=3548 string=0 first=
LEAD /home/username/seed7/lib/editline.s7i CLEAN errors=0 records=3548 string=10 first=
DRIVER /home/username/seed7/lib/elf.s7i CLEAN errors=0 records=6497 string=0 first=
LEAD /home/username/seed7/lib/elf.s7i CLEAN errors=0 records=6497 string=287 first=
DRIVER /home/username/seed7/lib/elliptic.s7i CLEAN errors=0 records=4489 string=0 first=
LEAD /home/username/seed7/lib/elliptic.s7i CLEAN errors=0 records=4489 string=43 first=
DRIVER /home/username/seed7/lib/enable_io.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/enable_io.s7i NOISY errors=10 records=3060 string=0 first=Redeclaration of "IN"
DRIVER /home/username/seed7/lib/encoding.s7i CLEAN errors=0 records=4277 string=0 first=
LEAD /home/username/seed7/lib/encoding.s7i CLEAN errors=0 records=4277 string=26 first=
DRIVER /home/username/seed7/lib/enumeration.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/enumeration.s7i NOISY errors=4 records=3060 string=0 first=Redeclaration of "expr_to_list (ref expr: elem_expr)"
DRIVER /home/username/seed7/lib/environment.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/environment.s7i NOISY errors=24 records=3060 string=0 first=Redeclaration of "PROGRAM argv"
DRIVER /home/username/seed7/lib/exif.s7i CLEAN errors=0 records=5538 string=0 first=
LEAD /home/username/seed7/lib/exif.s7i CLEAN errors=0 records=5538 string=40 first=
DRIVER /home/username/seed7/lib/external_file.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/external_file.s7i NOISY errors=44 records=3060 string=0 first=Redeclaration of "external_file"
DRIVER /home/username/seed7/lib/field.s7i CLEAN errors=0 records=3709 string=0 first=
LEAD /home/username/seed7/lib/field.s7i CLEAN errors=0 records=3709 string=7 first=
DRIVER /home/username/seed7/lib/filebits.s7i CLEAN errors=0 records=3677 string=0 first=
LEAD /home/username/seed7/lib/filebits.s7i CLEAN errors=0 records=3677 string=12 first=
DRIVER /home/username/seed7/lib/file.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/file.s7i NOISY errors=72 records=3060 string=0 first=Redeclaration of "file"
DRIVER /home/username/seed7/lib/filesys.s7i CLEAN errors=0 records=4097 string=0 first=
LEAD /home/username/seed7/lib/filesys.s7i CLEAN errors=0 records=4097 string=72 first=
DRIVER /home/username/seed7/lib/fileutil.s7i CLEAN errors=0 records=3064 string=0 first=
LEAD /home/username/seed7/lib/fileutil.s7i CLEAN errors=0 records=3064 string=4 first=
DRIVER /home/username/seed7/lib/fixarray.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/fixarray.s7i NOISY errors=4 records=3060 string=0 first=Redeclaration of "array [ (val integer: minIdx) .. (val integer: maxIdx) ] (val type: baseType)"
DRIVER /home/username/seed7/lib/float.s7i CLEAN errors=0 records=3338 string=0 first=
LEAD /home/username/seed7/lib/float.s7i CLEAN errors=0 records=3338 string=57 first=
DRIVER /home/username/seed7/lib/font8x8.s7i CLEAN errors=0 records=6823 string=0 first=
LEAD /home/username/seed7/lib/font8x8.s7i CLEAN errors=0 records=6823 string=2 first=
DRIVER /home/username/seed7/lib/font.s7i CLEAN errors=0 records=3237 string=0 first=
LEAD /home/username/seed7/lib/font.s7i CLEAN errors=0 records=3237 string=24 first=
DRIVER /home/username/seed7/lib/forloop.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/forloop.s7i NOISY errors=36 records=3060 string=0 first=Redeclaration of "for (inout integer: aVar) range (val integer: lowerLimit) to (val integer: upperLimit) do (ref proc: statements) end for"
DRIVER /home/username/seed7/lib/ftp.s7i CLEAN errors=0 records=5017 string=0 first=
LEAD /home/username/seed7/lib/ftp.s7i CLEAN errors=0 records=5017 string=49 first=
DRIVER /home/username/seed7/lib/ftpserv.s7i CLEAN errors=0 records=5283 string=0 first=
LEAD /home/username/seed7/lib/ftpserv.s7i CLEAN errors=0 records=5283 string=21 first=
DRIVER /home/username/seed7/lib/getf.s7i CLEAN errors=0 records=3064 string=0 first=
LEAD /home/username/seed7/lib/getf.s7i CLEAN errors=0 records=3064 string=4 first=
DRIVER /home/username/seed7/lib/gethttp.s7i CLEAN errors=0 records=8603 string=0 first=
LEAD /home/username/seed7/lib/gethttp.s7i CLEAN errors=0 records=8603 string=1 first=
DRIVER /home/username/seed7/lib/gethttps.s7i CLEAN errors=0 records=13797 string=0 first=
LEAD /home/username/seed7/lib/gethttps.s7i CLEAN errors=0 records=13797 string=1 first=
DRIVER /home/username/seed7/lib/gif.s7i CLEAN errors=0 records=7158 string=0 first=
LEAD /home/username/seed7/lib/gif.s7i CLEAN errors=0 records=7158 string=36 first=
DRIVER /home/username/seed7/lib/graph_file.s7i CLEAN errors=0 records=5360 string=0 first=
LEAD /home/username/seed7/lib/graph_file.s7i CLEAN errors=0 records=5360 string=30 first=
DRIVER /home/username/seed7/lib/graph.s7i CLEAN errors=0 records=4343 string=0 first=
LEAD /home/username/seed7/lib/graph.s7i CLEAN errors=0 records=4343 string=67 first=
DRIVER /home/username/seed7/lib/gtkserver.s7i CLEAN errors=0 records=3643 string=0 first=
LEAD /home/username/seed7/lib/gtkserver.s7i CLEAN errors=0 records=3643 string=8 first=
DRIVER /home/username/seed7/lib/gzip.s7i CLEAN errors=0 records=7365 string=0 first=
LEAD /home/username/seed7/lib/gzip.s7i CLEAN errors=0 records=7365 string=27 first=
DRIVER /home/username/seed7/lib/hash.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/hash.s7i NOISY errors=2 records=3060 string=0 first=Redeclaration of "hash [ (val type: keyType) ] (val type: baseType)"
DRIVER /home/username/seed7/lib/hashsetof.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/hashsetof.s7i NOISY errors=2 records=3060 string=0 first=Redeclaration of "hashset (val type: baseType)"
DRIVER /home/username/seed7/lib/hmac.s7i CLEAN errors=0 records=6131 string=0 first=
LEAD /home/username/seed7/lib/hmac.s7i CLEAN errors=0 records=6131 string=6 first=
DRIVER /home/username/seed7/lib/htmldom.s7i CLEAN errors=0 records=4820 string=0 first=
LEAD /home/username/seed7/lib/htmldom.s7i CLEAN errors=0 records=4820 string=11 first=
DRIVER /home/username/seed7/lib/html_ent.s7i CLEAN errors=0 records=3913 string=0 first=
LEAD /home/username/seed7/lib/html_ent.s7i CLEAN errors=0 records=3913 string=13 first=
DRIVER /home/username/seed7/lib/html.s7i CLEAN errors=0 records=3141 string=0 first=
LEAD /home/username/seed7/lib/html.s7i CLEAN errors=0 records=3141 string=3 first=
DRIVER /home/username/seed7/lib/http_request.s7i CLEAN errors=0 records=8602 string=0 first=
LEAD /home/username/seed7/lib/http_request.s7i CLEAN errors=0 records=8602 string=100 first=
DRIVER /home/username/seed7/lib/httpserv.s7i CLEAN errors=0 records=12319 string=0 first=
LEAD /home/username/seed7/lib/httpserv.s7i CLEAN errors=0 records=12319 string=15 first=
DRIVER /home/username/seed7/lib/https_request.s7i CLEAN errors=0 records=13796 string=0 first=
LEAD /home/username/seed7/lib/https_request.s7i CLEAN errors=0 records=13796 string=14 first=
DRIVER /home/username/seed7/lib/http_srv_resp.s7i CLEAN errors=0 records=13184 string=0 first=
LEAD /home/username/seed7/lib/http_srv_resp.s7i CLEAN errors=0 records=13184 string=10 first=
DRIVER /home/username/seed7/lib/huffman.s7i CLEAN errors=0 records=6041 string=0 first=
LEAD /home/username/seed7/lib/huffman.s7i CLEAN errors=0 records=6041 string=31 first=
DRIVER /home/username/seed7/lib/ico.s7i CLEAN errors=0 records=10623 string=0 first=
LEAD /home/username/seed7/lib/ico.s7i CLEAN errors=0 records=10623 string=9 first=
DRIVER /home/username/seed7/lib/idxarray.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/idxarray.s7i NOISY errors=4 records=3060 string=0 first=Redeclaration of "array [ (val type: indexType) ] (val type: baseType)"
DRIVER /home/username/seed7/lib/imagefile.s7i CLEAN errors=0 records=12968 string=0 first=
LEAD /home/username/seed7/lib/imagefile.s7i CLEAN errors=0 records=12968 string=3 first=
DRIVER /home/username/seed7/lib/image.s7i CLEAN errors=0 records=5314 string=0 first=
LEAD /home/username/seed7/lib/image.s7i CLEAN errors=0 records=5314 string=21 first=
DRIVER /home/username/seed7/lib/inflate.s7i CLEAN errors=0 records=6056 string=0 first=
LEAD /home/username/seed7/lib/inflate.s7i CLEAN errors=0 records=6056 string=15 first=
DRIVER /home/username/seed7/lib/inifile.s7i CLEAN errors=0 records=3712 string=0 first=
LEAD /home/username/seed7/lib/inifile.s7i CLEAN errors=0 records=3712 string=7 first=
DRIVER /home/username/seed7/lib/integer.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/integer.s7i NOISY errors=118 records=3060 string=0 first=Redeclaration of "(ref integer: dest) ::= (ref integer: source)"
DRIVER /home/username/seed7/lib/iobuffer.s7i CLEAN errors=0 records=3457 string=0 first=
LEAD /home/username/seed7/lib/iobuffer.s7i CLEAN errors=0 records=3457 string=21 first=
DRIVER /home/username/seed7/lib/jpeg.s7i CLEAN errors=0 records=8628 string=0 first=
LEAD /home/username/seed7/lib/jpeg.s7i CLEAN errors=0 records=8628 string=78 first=
DRIVER /home/username/seed7/lib/json.s7i CLEAN errors=0 records=4903 string=0 first=
LEAD /home/username/seed7/lib/json.s7i CLEAN errors=0 records=4903 string=92 first=
DRIVER /home/username/seed7/lib/json_serde.s7i CLEAN errors=0 records=4279 string=0 first=
LEAD /home/username/seed7/lib/json_serde.s7i CLEAN errors=0 records=4279 string=44 first=
DRIVER /home/username/seed7/lib/keybd.s7i CLEAN errors=0 records=3482 string=0 first=
LEAD /home/username/seed7/lib/keybd.s7i CLEAN errors=0 records=3482 string=284 first=
DRIVER /home/username/seed7/lib/keydescr.s7i CLEAN errors=0 records=3831 string=0 first=
LEAD /home/username/seed7/lib/keydescr.s7i CLEAN errors=0 records=3831 string=3 first=
DRIVER /home/username/seed7/lib/leb128.s7i CLEAN errors=0 records=3067 string=0 first=
LEAD /home/username/seed7/lib/leb128.s7i CLEAN errors=0 records=3067 string=7 first=
DRIVER /home/username/seed7/lib/line.s7i CLEAN errors=0 records=3116 string=0 first=
LEAD /home/username/seed7/lib/line.s7i CLEAN errors=0 records=3116 string=8 first=
DRIVER /home/username/seed7/lib/listener.s7i CLEAN errors=0 records=3768 string=0 first=
LEAD /home/username/seed7/lib/listener.s7i CLEAN errors=0 records=3768 string=11 first=
DRIVER /home/username/seed7/lib/logfile.s7i CLEAN errors=0 records=3104 string=0 first=
LEAD /home/username/seed7/lib/logfile.s7i CLEAN errors=0 records=3104 string=3 first=
DRIVER /home/username/seed7/lib/lower.s7i CLEAN errors=0 records=3116 string=0 first=
LEAD /home/username/seed7/lib/lower.s7i CLEAN errors=0 records=3116 string=10 first=
DRIVER /home/username/seed7/lib/lzma.s7i CLEAN errors=0 records=6107 string=0 first=
LEAD /home/username/seed7/lib/lzma.s7i CLEAN errors=0 records=6107 string=82 first=
DRIVER /home/username/seed7/lib/lzw.s7i CLEAN errors=0 records=5906 string=0 first=
LEAD /home/username/seed7/lib/lzw.s7i CLEAN errors=0 records=5906 string=23 first=
DRIVER /home/username/seed7/lib/magic.s7i CLEAN errors=0 records=4271 string=0 first=
LEAD /home/username/seed7/lib/magic.s7i CLEAN errors=0 records=4271 string=57 first=
DRIVER /home/username/seed7/lib/mahjng32.s7i CLEAN errors=0 records=5240 string=0 first=
LEAD /home/username/seed7/lib/mahjng32.s7i CLEAN errors=0 records=5240 string=42 first=
DRIVER /home/username/seed7/lib/makedata.s7i CLEAN errors=0 records=5896 string=0 first=
LEAD /home/username/seed7/lib/makedata.s7i CLEAN errors=0 records=5896 string=51 first=
DRIVER /home/username/seed7/lib/make.s7i CLEAN errors=0 records=6230 string=0 first=
LEAD /home/username/seed7/lib/make.s7i CLEAN errors=0 records=6230 string=19 first=
DRIVER /home/username/seed7/lib/math.s7i CLEAN errors=0 records=3357 string=0 first=
LEAD /home/username/seed7/lib/math.s7i CLEAN errors=0 records=3357 string=19 first=
DRIVER /home/username/seed7/lib/mixarith.s7i CLEAN errors=0 records=3943 string=0 first=
LEAD /home/username/seed7/lib/mixarith.s7i CLEAN errors=0 records=3943 string=25 first=
DRIVER /home/username/seed7/lib/modern27.s7i CLEAN errors=0 records=6972 string=0 first=
LEAD /home/username/seed7/lib/modern27.s7i NOISY errors=95 records=6972 string=2 first="'" expected found "\194;" (U+00c2)
DRIVER /home/username/seed7/lib/more.s7i CLEAN errors=0 records=3120 string=0 first=
LEAD /home/username/seed7/lib/more.s7i CLEAN errors=0 records=3120 string=4 first=
DRIVER /home/username/seed7/lib/msgdigest.s7i CLEAN errors=0 records=6125 string=0 first=
LEAD /home/username/seed7/lib/msgdigest.s7i CLEAN errors=0 records=6125 string=61 first=
DRIVER /home/username/seed7/lib/multiscr.s7i NOISY errors=2 records=4094 string=0 first=Match for openWindow(SCR, 2, 2, 10, 78) failed
LEAD /home/username/seed7/lib/multiscr.s7i NOISY errors=2 records=4094 string=5 first=Match for openWindow(SCR, 2, 2, 10, 78) failed
DRIVER /home/username/seed7/lib/null_file.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/null_file.s7i NOISY errors=44 records=3060 string=0 first=Redeclaration of "null_file"
DRIVER /home/username/seed7/lib/osfiles.s7i CLEAN errors=0 records=4234 string=0 first=
LEAD /home/username/seed7/lib/osfiles.s7i CLEAN errors=0 records=4234 string=86 first=
DRIVER /home/username/seed7/lib/pbm.s7i CLEAN errors=0 records=5968 string=0 first=
LEAD /home/username/seed7/lib/pbm.s7i CLEAN errors=0 records=5968 string=9 first=
DRIVER /home/username/seed7/lib/pcx.s7i CLEAN errors=0 records=5576 string=0 first=
LEAD /home/username/seed7/lib/pcx.s7i CLEAN errors=0 records=5576 string=42 first=
DRIVER /home/username/seed7/lib/pem.s7i CLEAN errors=0 records=4676 string=0 first=
LEAD /home/username/seed7/lib/pem.s7i CLEAN errors=0 records=4676 string=9 first=
DRIVER /home/username/seed7/lib/pgm.s7i CLEAN errors=0 records=5969 string=0 first=
LEAD /home/username/seed7/lib/pgm.s7i CLEAN errors=0 records=5969 string=10 first=
DRIVER /home/username/seed7/lib/pic16.s7i CLEAN errors=0 records=5251 string=0 first=
LEAD /home/username/seed7/lib/pic16.s7i CLEAN errors=0 records=5251 string=53 first=
DRIVER /home/username/seed7/lib/pic32.s7i CLEAN errors=0 records=5256 string=0 first=
LEAD /home/username/seed7/lib/pic32.s7i CLEAN errors=0 records=5256 string=58 first=
DRIVER /home/username/seed7/lib/pic_util.s7i CLEAN errors=0 records=5198 string=0 first=
LEAD /home/username/seed7/lib/pic_util.s7i CLEAN errors=0 records=5198 string=3 first=
DRIVER /home/username/seed7/lib/pixelimage.s7i CLEAN errors=0 records=5458 string=0 first=
LEAD /home/username/seed7/lib/pixelimage.s7i CLEAN errors=0 records=5458 string=15 first=
DRIVER /home/username/seed7/lib/pixel.s7i CLEAN errors=0 records=3250 string=0 first=
LEAD /home/username/seed7/lib/pixel.s7i CLEAN errors=0 records=3250 string=16 first=
DRIVER /home/username/seed7/lib/pixmap_file.s7i CLEAN errors=0 records=6526 string=0 first=
LEAD /home/username/seed7/lib/pixmap_file.s7i CLEAN errors=0 records=6526 string=29 first=
DRIVER /home/username/seed7/lib/pixmapfont.s7i CLEAN errors=0 records=6364 string=0 first=
LEAD /home/username/seed7/lib/pixmapfont.s7i CLEAN errors=0 records=6364 string=34 first=
DRIVER /home/username/seed7/lib/pkcs1.s7i CLEAN errors=0 records=6244 string=0 first=
LEAD /home/username/seed7/lib/pkcs1.s7i CLEAN errors=0 records=6244 string=27 first=
DRIVER /home/username/seed7/lib/png.s7i CLEAN errors=0 records=8519 string=0 first=
LEAD /home/username/seed7/lib/png.s7i CLEAN errors=0 records=8519 string=50 first=
DRIVER /home/username/seed7/lib/poll.s7i CLEAN errors=0 records=3694 string=0 first=
LEAD /home/username/seed7/lib/poll.s7i CLEAN errors=0 records=3694 string=30 first=
DRIVER /home/username/seed7/lib/ppm.s7i CLEAN errors=0 records=5969 string=0 first=
LEAD /home/username/seed7/lib/ppm.s7i CLEAN errors=0 records=5969 string=10 first=
DRIVER /home/username/seed7/lib/process.s7i CLEAN errors=0 records=5274 string=0 first=
LEAD /home/username/seed7/lib/process.s7i CLEAN errors=0 records=5274 string=36 first=
DRIVER /home/username/seed7/lib/progs.s7i CLEAN errors=0 records=7994 string=0 first=
LEAD /home/username/seed7/lib/progs.s7i CLEAN errors=0 records=7994 string=187 first=
DRIVER /home/username/seed7/lib/propertyfile.s7i CLEAN errors=0 records=3560 string=0 first=
LEAD /home/username/seed7/lib/propertyfile.s7i CLEAN errors=0 records=3560 string=6 first=
DRIVER /home/username/seed7/lib/rational.s7i CLEAN errors=0 records=3640 string=0 first=
LEAD /home/username/seed7/lib/rational.s7i CLEAN errors=0 records=3640 string=43 first=
DRIVER /home/username/seed7/lib/reference.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/reference.s7i NOISY errors=42 records=3060 string=0 first=Redeclaration of "reference"
DRIVER /home/username/seed7/lib/ref_list.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/ref_list.s7i NOISY errors=58 records=3060 string=0 first=Redeclaration of "ref_list"
DRIVER /home/username/seed7/lib/reverse.s7i CLEAN errors=0 records=3114 string=0 first=
LEAD /home/username/seed7/lib/reverse.s7i CLEAN errors=0 records=3114 string=6 first=
DRIVER /home/username/seed7/lib/rpmext.s7i CLEAN errors=0 records=17509 string=0 first=
LEAD /home/username/seed7/lib/rpmext.s7i CLEAN errors=0 records=17509 string=30 first=
DRIVER /home/username/seed7/lib/rpm.s7i CLEAN errors=0 records=17479 string=0 first=
LEAD /home/username/seed7/lib/rpm.s7i CLEAN errors=0 records=17479 string=469 first=
DRIVER /home/username/seed7/lib/scanfile.s7i CLEAN errors=0 records=3139 string=0 first=
LEAD /home/username/seed7/lib/scanfile.s7i CLEAN errors=0 records=3139 string=42 first=
DRIVER /home/username/seed7/lib/scanjson.s7i CLEAN errors=0 records=3103 string=0 first=
LEAD /home/username/seed7/lib/scanjson.s7i CLEAN errors=0 records=3103 string=6 first=
DRIVER /home/username/seed7/lib/scanstri.s7i CLEAN errors=0 records=3138 string=0 first=
LEAD /home/username/seed7/lib/scanstri.s7i CLEAN errors=0 records=3138 string=41 first=
DRIVER /home/username/seed7/lib/scantoml.s7i CLEAN errors=0 records=3286 string=0 first=
LEAD /home/username/seed7/lib/scantoml.s7i CLEAN errors=0 records=3286 string=43 first=
DRIVER /home/username/seed7/lib/seed7_05.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/seed7_05.s7i NOISY errors=390 records=3061 string=1 first=Redeclaration of "func (ref type param)"
RECORDS-DIFF /home/username/seed7/lib/seed7_05.s7i driver=3060 lead=3061
DRIVER /home/username/seed7/lib/set.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/set.s7i NOISY errors=2 records=3060 string=0 first=Redeclaration of "set of (val type: baseType)"
DRIVER /home/username/seed7/lib/shell.s7i CLEAN errors=0 records=3331 string=0 first=
LEAD /home/username/seed7/lib/shell.s7i CLEAN errors=0 records=3331 string=22 first=
DRIVER /home/username/seed7/lib/shiftjis.s7i CLEAN errors=0 records=3758 string=0 first=
LEAD /home/username/seed7/lib/shiftjis.s7i NOISY errors=1214 records=3758 string=6 first="'" expected found "\194;" (U+00c2)
DRIVER /home/username/seed7/lib/showtls.s7i CLEAN errors=0 records=11508 string=0 first=
LEAD /home/username/seed7/lib/showtls.s7i CLEAN errors=0 records=11508 string=18 first=
DRIVER /home/username/seed7/lib/signature.s7i CLEAN errors=0 records=7146 string=0 first=
LEAD /home/username/seed7/lib/signature.s7i CLEAN errors=0 records=7146 string=5 first=
DRIVER /home/username/seed7/lib/smtp.s7i CLEAN errors=0 records=11657 string=0 first=
LEAD /home/username/seed7/lib/smtp.s7i CLEAN errors=0 records=11657 string=10 first=
DRIVER /home/username/seed7/lib/sockbase.s7i CLEAN errors=0 records=3166 string=0 first=
LEAD /home/username/seed7/lib/sockbase.s7i CLEAN errors=0 records=3166 string=48 first=
DRIVER /home/username/seed7/lib/socket.s7i CLEAN errors=0 records=3635 string=0 first=
LEAD /home/username/seed7/lib/socket.s7i CLEAN errors=0 records=3635 string=42 first=
DRIVER /home/username/seed7/lib/sokoban1.s7i CLEAN errors=0 records=3182 string=0 first=
LEAD /home/username/seed7/lib/sokoban1.s7i CLEAN errors=0 records=3182 string=1 first=
DRIVER /home/username/seed7/lib/sql_base.s7i CLEAN errors=0 records=5164 string=0 first=
LEAD /home/username/seed7/lib/sql_base.s7i CLEAN errors=0 records=5164 string=93 first=
DRIVER /home/username/seed7/lib/stars.s7i CLEAN errors=0 records=3493 string=0 first=
LEAD /home/username/seed7/lib/stars.s7i CLEAN errors=0 records=3493 string=3 first=
DRIVER /home/username/seed7/lib/stdfont10.s7i CLEAN errors=0 records=6823 string=0 first=
LEAD /home/username/seed7/lib/stdfont10.s7i NOISY errors=99 records=6823 string=2 first="'" expected found "\194;" (U+00c2)
DRIVER /home/username/seed7/lib/stdfont12.s7i CLEAN errors=0 records=6823 string=0 first=
LEAD /home/username/seed7/lib/stdfont12.s7i NOISY errors=99 records=6823 string=2 first="'" expected found "\194;" (U+00c2)
DRIVER /home/username/seed7/lib/stdfont14.s7i CLEAN errors=0 records=6823 string=0 first=
LEAD /home/username/seed7/lib/stdfont14.s7i NOISY errors=99 records=6823 string=2 first="'" expected found "\194;" (U+00c2)
DRIVER /home/username/seed7/lib/stdfont16.s7i CLEAN errors=0 records=6823 string=0 first=
LEAD /home/username/seed7/lib/stdfont16.s7i NOISY errors=99 records=6823 string=2 first="'" expected found "\194;" (U+00c2)
DRIVER /home/username/seed7/lib/stdfont18.s7i CLEAN errors=0 records=6823 string=0 first=
LEAD /home/username/seed7/lib/stdfont18.s7i NOISY errors=99 records=6823 string=2 first="'" expected found "\194;" (U+00c2)
DRIVER /home/username/seed7/lib/stdfont20.s7i CLEAN errors=0 records=6823 string=0 first=
LEAD /home/username/seed7/lib/stdfont20.s7i NOISY errors=99 records=6823 string=2 first="'" expected found "\194;" (U+00c2)
DRIVER /home/username/seed7/lib/stdfont24.s7i CLEAN errors=0 records=6823 string=0 first=
LEAD /home/username/seed7/lib/stdfont24.s7i NOISY errors=99 records=6823 string=2 first="'" expected found "\194;" (U+00c2)
DRIVER /home/username/seed7/lib/stdfont8.s7i CLEAN errors=0 records=6823 string=0 first=
LEAD /home/username/seed7/lib/stdfont8.s7i NOISY errors=99 records=6823 string=2 first="'" expected found "\194;" (U+00c2)
DRIVER /home/username/seed7/lib/stdfont9.s7i CLEAN errors=0 records=6823 string=0 first=
LEAD /home/username/seed7/lib/stdfont9.s7i NOISY errors=99 records=6823 string=2 first="'" expected found "\194;" (U+00c2)
DRIVER /home/username/seed7/lib/stdio.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/stdio.s7i NOISY errors=30 records=3060 string=0 first=Redeclaration of "INIT_STD_FILE (ref clib_file: primitive_file, ref string: fileName)"
DRIVER /home/username/seed7/lib/strifile.s7i CLEAN errors=0 records=3132 string=0 first=
LEAD /home/username/seed7/lib/strifile.s7i CLEAN errors=0 records=3132 string=17 first=
DRIVER /home/username/seed7/lib/string.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/string.s7i NOISY errors=120 records=3060 string=0 first=Redeclaration of "(ref string: dest) ::= (ref string: source)"
DRIVER /home/username/seed7/lib/stritext.s7i CLEAN errors=0 records=3300 string=0 first=
LEAD /home/username/seed7/lib/stritext.s7i CLEAN errors=0 records=3300 string=30 first=
DRIVER /home/username/seed7/lib/struct_elem.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/struct_elem.s7i NOISY errors=30 records=3060 string=0 first=Redeclaration of "structElement"
DRIVER /home/username/seed7/lib/struct.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/struct.s7i NOISY errors=30 records=3060 string=0 first=Redeclaration of "STRUCT"
DRIVER /home/username/seed7/lib/subfile.s7i CLEAN errors=0 records=3129 string=0 first=
LEAD /home/username/seed7/lib/subfile.s7i CLEAN errors=0 records=3129 string=10 first=
DRIVER /home/username/seed7/lib/subrange.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/subrange.s7i NOISY errors=2 records=3060 string=0 first=Redeclaration of "SUBRANGE_TYPES (val type: baseType)"
DRIVER /home/username/seed7/lib/syntax.s7i CLEAN errors=0 records=3060 string=0 first=
LEAD /home/username/seed7/lib/syntax.s7i NOISY errors=249 records=3060 string=0 first=Redeclaration of "type"
DRIVER /home/username/seed7/lib/tar_cmds.s7i CLEAN errors=0 records=20021 string=0 first=
LEAD /home/username/seed7/lib/tar_cmds.s7i CLEAN errors=0 records=20021 string=19 first=
DRIVER /home/username/seed7/lib/tar.s7i CLEAN errors=0 records=5355 string=0 first=
LEAD /home/username/seed7/lib/tar.s7i CLEAN errors=0 records=5355 string=74 first=
DRIVER /home/username/seed7/lib/tdes.s7i CLEAN errors=0 records=5601 string=0 first=
LEAD /home/username/seed7/lib/tdes.s7i CLEAN errors=0 records=5601 string=6 first=
DRIVER /home/username/seed7/lib/tee.s7i CLEAN errors=0 records=3236 string=0 first=
LEAD /home/username/seed7/lib/tee.s7i CLEAN errors=0 records=3236 string=10 first=
DRIVER /home/username/seed7/lib/text.s7i CLEAN errors=0 records=3213 string=0 first=
LEAD /home/username/seed7/lib/text.s7i CLEAN errors=0 records=3213 string=20 first=
DRIVER /home/username/seed7/lib/tga.s7i CLEAN errors=0 records=5569 string=0 first=
LEAD /home/username/seed7/lib/tga.s7i CLEAN errors=0 records=5569 string=39 first=
DRIVER /home/username/seed7/lib/tiff.s7i CLEAN errors=0 records=11563 string=0 first=
LEAD /home/username/seed7/lib/tiff.s7i CLEAN errors=0 records=11563 string=154 first=
DRIVER /home/username/seed7/lib/time.s7i CLEAN errors=0 records=3206 string=0 first=
LEAD /home/username/seed7/lib/time.s7i CLEAN errors=0 records=3206 string=64 first=
DRIVER /home/username/seed7/lib/tls.s7i CLEAN errors=0 records=11490 string=0 first=
LEAD /home/username/seed7/lib/tls.s7i CLEAN errors=0 records=11490 string=201 first=
DRIVER /home/username/seed7/lib/unicode.s7i CLEAN errors=0 records=3074 string=0 first=
LEAD /home/username/seed7/lib/unicode.s7i CLEAN errors=0 records=3074 string=14 first=
DRIVER /home/username/seed7/lib/unionfnd.s7i CLEAN errors=0 records=3111 string=0 first=
LEAD /home/username/seed7/lib/unionfnd.s7i CLEAN errors=0 records=3111 string=7 first=
DRIVER /home/username/seed7/lib/upper.s7i CLEAN errors=0 records=3116 string=0 first=
LEAD /home/username/seed7/lib/upper.s7i CLEAN errors=0 records=3116 string=10 first=
DRIVER /home/username/seed7/lib/utf16.s7i CLEAN errors=0 records=3215 string=0 first=
LEAD /home/username/seed7/lib/utf16.s7i CLEAN errors=0 records=3215 string=19 first=
DRIVER /home/username/seed7/lib/utf8.s7i CLEAN errors=0 records=3129 string=0 first=
LEAD /home/username/seed7/lib/utf8.s7i CLEAN errors=0 records=3129 string=18 first=
DRIVER /home/username/seed7/lib/vecfont10.s7i CLEAN errors=0 records=6972 string=0 first=
LEAD /home/username/seed7/lib/vecfont10.s7i NOISY errors=99 records=6972 string=2 first="'" expected found "\194;" (U+00c2)
DRIVER /home/username/seed7/lib/vecfont18.s7i CLEAN errors=0 records=6972 string=0 first=
LEAD /home/username/seed7/lib/vecfont18.s7i NOISY errors=99 records=6972 string=2 first="'" expected found "\194;" (U+00c2)
DRIVER /home/username/seed7/lib/vector3d.s7i CLEAN errors=0 records=3431 string=0 first=
LEAD /home/username/seed7/lib/vector3d.s7i CLEAN errors=0 records=3431 string=22 first=
DRIVER /home/username/seed7/lib/vectorfont.s7i CLEAN errors=0 records=6970 string=0 first=
LEAD /home/username/seed7/lib/vectorfont.s7i CLEAN errors=0 records=6970 string=13 first=
DRIVER /home/username/seed7/lib/wildcard.s7i CLEAN errors=0 records=4237 string=0 first=
LEAD /home/username/seed7/lib/wildcard.s7i CLEAN errors=0 records=4237 string=3 first=
DRIVER /home/username/seed7/lib/window.s7i CLEAN errors=0 records=3305 string=0 first=
LEAD /home/username/seed7/lib/window.s7i CLEAN errors=0 records=3305 string=27 first=
DRIVER /home/username/seed7/lib/wrinum.s7i CLEAN errors=0 records=3063 string=0 first=
LEAD /home/username/seed7/lib/wrinum.s7i CLEAN errors=0 records=3063 string=3 first=
DRIVER /home/username/seed7/lib/x509cert.s7i CLEAN errors=0 records=8725 string=0 first=
LEAD /home/username/seed7/lib/x509cert.s7i CLEAN errors=0 records=8725 string=63 first=
DRIVER /home/username/seed7/lib/xmldom.s7i CLEAN errors=0 records=4722 string=0 first=
LEAD /home/username/seed7/lib/xmldom.s7i CLEAN errors=0 records=4722 string=28 first=
DRIVER /home/username/seed7/lib/xml_ent.s7i CLEAN errors=0 records=3410 string=0 first=
LEAD /home/username/seed7/lib/xml_ent.s7i CLEAN errors=0 records=3410 string=4 first=
DRIVER /home/username/seed7/lib/xz.s7i CLEAN errors=0 records=9043 string=0 first=
LEAD /home/username/seed7/lib/xz.s7i CLEAN errors=0 records=9043 string=39 first=
DRIVER /home/username/seed7/lib/zip.s7i CLEAN errors=0 records=14927 string=0 first=
LEAD /home/username/seed7/lib/zip.s7i CLEAN errors=0 records=14927 string=129 first=
DRIVER /home/username/seed7/lib/zstd.s7i CLEAN errors=0 records=6396 string=0 first=
LEAD /home/username/seed7/lib/zstd.s7i CLEAN errors=0 records=6396 string=65 first=
CONTROL /home/username/seed7/prg/hello.sd7 CLEAN errors=0 records=3061 string=1 first=
SENTINEL files=214 leadClean=168 leadNoisy=46 recordsSame=213
