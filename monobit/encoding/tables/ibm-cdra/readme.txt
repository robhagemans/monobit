Note:

This material and the conversion resources were updated in December 2013.  New Unicode tables 
were added and a few mappings were updated.  Note that the naming convension for the Unicode
tables is IBM-nnnn where the nnnn is the 
non-unicode 'code page'.  PACKAGE1 conatins all of the conversion tables that map from a
single-byte encoding to and from Unicode and PACKAGE2 contains all of the conversion tables that 
map from a multi-byte encoding to and from Unicode.  In addition PACKAGE6 was updated. This package
contains all of the new, non-unicode conversion tables that have been created since the last 
refresh of this material in November of 2006.  If you can not find the conversion resource that
you require please contact the Globalization Center of Competency in Toronto at GCOC@ca.ibm.com.



Terminology

The terminology for character data encoding varies from corporation to corporation and 
even from platform to platform within a corporation.  The term "code page" is used 
here as the name of the identifier whose value is commonly used to describe the encoding
of data.  It may be a true IBM code page value such as 500 which is an EBCDIC, International 
Latin-1 code or it may be a CCSID (Coded Character Set Identifier) such as 932 which 
represents the mixed, single-byte (code page 897), double-byte (code page 301) ASCII 
encoding for Japan.  AIX uses the term code set to describe a data encoding.  

Further information on CCSIDs can be found in Character Data Representation Architecture 
Reference and Registry publication (IBM document number SC09-2190).  The most recent version
of this publication is available on-line at 

http://www-01.ibm.com/software/globalization/cdra/index.html


Introduction  

The IBM Globalization Center of Competency (GCoC) has created a registry of character
data conversion tables.  The content of this registry is now available here, through 
developerWorks.

A conversion table contains the data required to map characters from one encoding to 
another.  In the attached zip files you will find binary conversion tables that provide
mappings between single-byte, double-byte, mixed single- and double-byte, Extended Unix
Code (EUC) and TCP/IP multi-byte, and UCS encodings.  Character data conversion is 
becoming more and more necessary as applications become less homogeneous; accepting data 
from various locations and producing output which is sent on to other applications, 
possibly on different systems in other parts of the world.  In order to minimize the loss
and misinterpretation of data, the data must be identified so that the receiving or processing
system can perform an appropriate data conversion if necessary.

The following sections of this document describe the various principles used in creating
the conversion tables, the naming convention and format of the tables and how to locate
and extract a specific table.


Mapping Algorithms

There are three main algorithms used for creating the conversion tables; round trip, 
enforced subset and customization.  All three algorithms begin by pairing the matching
characters from the source and target.  It is in the handling of the non-matching
characters that the algorithms vary.

Round Trip

The defining characteristic of a round trip conversion table is that if you map from a 
source encoding, A to a target encoding, B and then from B back to A you will get back
exactly what you started with providing no processing has been done on the data.  The
first step in round trip mapping is to pair all of the identical characters, next characters
defined to be synonyms are paired (these are characters which look the same but have
different names such as Greek letter Sigma and mathematical symbol sigma), finally all 
of the remaining characters will be mapped.  The algorithm used in the creation of most of
the round trip tables in the GCoC registry maps the pairs in sequential order (the first 
non-matching character from the source is mapped to the first non-matching 
character of the target).  Round trip conversion tables are primarily used for 
single-byte conversions when data is to be stored on one system and processed on another.

Enforced Subset

Like the round trip algorithm, the first steps in creating an enforced subset conversion
table are to map all of the identical characters and the defined synonyms.  Here the 
similarity ends.  All characters in the source code page which do not have an exact or
synonym match in the target are mapped to the defined SUBSTITUTE control 
character. Enforced subset tables are generally used when data is being imported into a 
system.  It is also used when mapping from a large set to a small set.  It is impossible
to provide unique mappings for every character when your source has several thousand defined 
characters and your target has only 256 characters as is the case when mapping from Unicode 
to a single-byte encoding. Most of the IBM tables for the far east, single-, double-,
and mixed single- double-byte are built using the enforced subset algorithm as are the 
Unicode tables.

Customization

Building a customized conversion table is done by first pairing all of the exact matches.
The remaining characters are mapped based on input from IBM country or language 
authorities. These tables are generally used within the non-Latin-1 countries. Languages 
such as Arabic and Farsi use different shapes for the same character depending on where it
is positioned within a word, initial, middle or final.  Some code pages contain all three
forms of the character while others contain only a single unshaped version of each 
character.  In this case when converting from the source code page to the target code page
the initial, middle and final instances of a specified character would all map to the 
unshaped version of that character in the target.  We end up with a 'many-to-one' mapping in 
the forward direction and a 'one-to-one' mapping in the reverse direction.  This results in 
some amount of data loss during an A - B - A conversion.


Table Creation Process

When a table is requested by IBM development, it is created by the GCoC using the most 
appropriate algorithm.  Once created, a review copy of the table is made available for the requeser 
and the IBM representatives in the geographical areas where the source and target
code pages are used. Comments from the reviewers are taken into consideration and changes 
are made if necessary. The completed tables are delivered to the requester and placed in the
registry making them available to the entire IBM development community.


Table Naming Convention

At the time this registry was first created it was hosted on a VM system.  A naming 
convention that used only eight characters for the file name and another eight characters
for the file type was required. The following convention was used in the naming of the files 
which contain the actual conversion tables.

The file name is eight characters long.  The first four characters are the source code 
page value in hex and the last four characters are the target code page value in hex. For
example a conversion table between code page 37 and code page 500 would be found in a file
with a file name of 002501F4.

The file type or extension is used to give the user more information about the type and format of
the table.  The extension, for binary tables, is in the form x-y-z where:

x can be - 	S = single-byte machine readable binary (1 record of 256 bytes) 
		D = double-byte machine readable binary (512 byte records) 
		E = EUC (Extended Unix Code) machine readable binary 
		T = machine readable TCP/IP conversion table
		SU = single-byte to Unicodemachine readable binary (1 record  of 512 bytes)
		US = unicode to single-byte machine readable binary (512 byte records) 
		MU = mixed to Unicode machine readable binary (512 byte records) 
		UM = unicode to mixed machine readable binary (512 byte records) 
		EU = EUC to unicode machine readable binary 
		UE = unicode to EUC machine readable binary	

y can be - 	E0 = enforced subset conversion algorithm
		Rx = round trip conversion algorithm x
		EC = enforced subset, customized
		RC = round trip, customized
		C0 = special case, customized table
		E = enforced subset (UCS-2 tables only)
		R = Semi-round trip (UCS-2 tables only)		
		    (The round trip only applies to conversions TO UCS-2 and back again. 
		     Conversion FROM UCS-2 are never round trip.)

z can be -  	D = Globalization Center of Competency recommended default mapping for the	
		    specified code page pair
		An = Alternate table number n for the specified code page pair

Some sample file extensions are shown in the following examples.

A table with the extension S-R2-D would be a single byte, 256 byte binary table, built 
using round trip algorithm number 2 and is the GCoC recommended default table.

A table with the extension MU-E-D would be a mixed single- double-byte to unicode binary
conversion table made up of 512 byte records and is the GCoC recommended default table.
 

Table Formats

This section provides some details of the conversion table formats found in the registry.
Complete details including pictorial examples are contained in Character Data 
Representation Architecture Reference and Registry publication (IBM document number 
SC09-2190). The most recent version of this publication is available on-line at: 

http://www-01.ibm.com/software/globalization/cdra/index.html

The specifics of the various character data conversion methods and the formats for the 
tables are found in Appendix B:

http://www-01.ibm.com/software/globalization/cdra/appendix_b.html

In addition to this documentation, some newer table packages, such as those in support of   
Chinese standard GB18030, contain specific documentation within the zip file. 

Single-byte Tables 

A single-byte binary conversion table is made up of one 256 byte record. Each byte in the record
corresponds to the source code input code points X'00' through X'FF'. The byte value in the
record is the code point value for the character in the target code.  For example, to find 
the output code point for the input code point X'40' you use this value as an index into
the table and find the code point value at the X'40' location in the record.  Remember when
counting that the first byte in the record is X'00' and not X'01'.

Double-byte Tables 

In order to accurately describe the format of the double-byte conversion we must first 
define the concept of a "ward".  A ward is a section of a double-byte code page.  All of
the code points contained in a specific ward begin with the same first byte.  A ward is
said to be populated if there are any characters in the double-byte code page whose first
byte is the ward value. 

A double-byte binary conversion table is made up of several 512 byte records.  The first
record acts as in index into the rest of the table.  There is one 512 byte record for each
populated ward in the source code page and one additional record for pairing invalid input
code points.  The table is used by separating the first and second bytes of the input
code point.  The first byte is used as a pointer into the index record.  The single byte 
value found at the corresponding position in the index gives the user the record number
in which to perform the second lookup.  The user then take the second byte of the input
code point and uses it as a pointer into the record specified by the index record. When
calculating the offset into this record there are two things to remember; first, you must 
begin counting at zero, and second, each entry is two bytes long.
For example if the input code point was X'41C1' you would find the single-byte table 
record number at the X'41' position in the index record.  The resultant double-byte output
code point would be found in the specified record number beginning at position X'182' (which
is two times X'C1') and again counting into the record starting at X'00'.  

The one additional record mentioned for handling invalid input data works as follows.  All
of the 256 double-byte code point values found in this record are those of the "Substitute"
character of the target code page.  All of the entries in the index record for unpopulated
wards point to this "substitute" record. 

Refer to the referenced material above for more detailed pictorial examples.

Unicode Tables

UCS-2 is essentially a double-byte encoding since every character is encoded using 2 bytes.

There are multiple formats available for mappings to and from UCS-2.  Table files with 
the extension RPMAPnnn, TPMAPnnn, and UPMAPnnn contain human readable formats.  They
have multiple columns containing the source code point value, the character "name" found 
at that code point and the target code point value.  Each file contains a brief header and
column descriptions.  In addition to the readable tables, binary formats are also included.
An overview of the binary formats is included below and found in the on-line documentation
referenced above. 

The single-byte to UCS-2 tables (file extension SU-y-z) consist of a single 512 byte record
(256 2-byte entries).  The source code point is used as a pointer to determine which 2
bytes in the table record represent the target code point.

The UCS-2 to single-byte tables are very similar to the double-byte tables described above 
except that each of the records contains only 256 bytes since the target code points are 
only a single byte in length.

Tables for mixed single-byte, double-byte codes to UCS-2 are the same as the double-byte tables 
described above.  All single-byte code points within the input stream must be normalized 
to a double-byte code by adding a leading zero byte prior to using the conversion table. 
Likewise when converting from UCS-2 to a mixed code the resultant single-bytes in the table
have been normalized with a leading zero byte.  When composing an output string the leading
zero byte must be removed.

For additional, more detailed information on the conversion tables and their 
formats refer to Character Data Representation Architecture Reference  
publication as indicated above.


EUC Tables

EUC (Extended Unix Code) tables are quite complex.  Each EUC encoding represents a 
collection of 3 or 4 single-byte and double-byte code pages.  For information on the 
format of the EUC tables please refer to the section on EUC conversions in Appendix B
of the on-line version of the CDRA Reference publication mentioned above or contact 
the GCoC directly at GCoC@ca.ibm.com.


How To Locate The Table You Want

When you downloaded this package, it included this README, a HINTS.TXT file and a file
called TABINDX.TXT.
The other zip files all contain collections of conversion tables.  Within each one of these
zip files there are many smaller zip files which contain a set of tables for a specific
pair of code pages and a text description file for the tables.

If you are looking for a table the place to start is in the HINTS file.  This file
contains useful information about the code page values used for some "special" encodings.
It will give you the code page value that has been used for UCS-2, it will give you the 	
code page values for code pages containing the new euro currency symbol and it may provide 
you with some useful information if you are looking for tables for non-IBM code pages.

The TABINDX.TXT file has been set up to help you locate a table.  Each record is 
made up of five columns. The first two columns contain the decimal values of the code page
source and target. The lower value is always in the first column.  If you are looking for a
conversion table for code page 850 to code page 500 you would look for the directory entry
with 500 in column one and 850 in column two.  The third column tells which zip file should	
be downloaded from DEVCON On-line.  Column four contains the name of the actual zip file 
containing the conversion table and column five contains a short somewhat cryptic 
description of the conversion pair.


Column 1    Column 2     Column 3    Column 4    Column 5

500         850          Package1    01F40352    CECP: Intl. Latin-1 -  PC Data: MLP 222; Latin 1;      


Column 1 - The lower value of the code page pair. A complete definition of this CCSID value can 
	   be found in the on-line CCSID resource located at:
	   http://www-306.ibm.com/software/globalization/ccsid/ccsid_registered.jsp
Column 2 - The higher value of the code page pair or in the case of Unicode UCS.
	   A complete definition of this CCSID value can 
	   be found in the on-line CCSID resource located at:
	   http://www-306.ibm.com/software/globalization/ccsid/ccsid_registered.jsp
Column 3 - The name of the PACKAGE Zip file that the tables are located in
Column 4 - The name of the zip file within the PACKAGE that contain all of the tables and 
           information for conversions between code pages 500 and 850 (Note: the first four
           characters in the name, 01F4, are the hex equivalent of 500 and the last four
           characters, 0352 are the hex equivalent of 850 except in the case of UCS tables
	   where the naming convention is IBM-nnnn where nnnn is the 'code page' of the 
	   non-unicode encoding)
Column 5 - A brief,  description of the source and target  
      

