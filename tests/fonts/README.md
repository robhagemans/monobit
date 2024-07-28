## Testing fonts

The fonts are included here for testing and some have been modified. If you wish to use these fonts
for other purposes, it is recommended that you download them from the original sources, not from here.

Original sources:
* `4x6.bdf`
  - https://www.cl.cam.ac.uk/~mgk25/ucs-fonts.html
  - in the public domain
* `6x13.fon` and `6x13.fd` (originally `fixed.*`)
  - https://www.chiark.greenend.org.uk/~sgtatham/fonts/
  - in the public domain
* `WebbySmall.fon` and `WebbySmall.pcf`
  - https://github.com/bluescan/proggyfonts/tree/master/ProggyOriginal
  - (c) 2004, 2005 Tristan Grimmer, released under an MIT licence
* `wbfont`
  - http://aminet.net/text/bfont/wbfont.lha
  - (c) 1999 Keith Halstead, free to distribute so long as the readme file is included
* `L2UNIVB18.FNT`
  - http://cd.textfiles.com/geminiatari/FILES/FONTS/GDOS/TWFNTSLA/
  - Bernie LaGrave / Ric Kalford
  - in the public domain
* `AI360GVP.VGA`
  - supplied with the GEM/3 screen drivers
  - http://www.deltasoft.com/downloads/screendr.zip
  - GNU General Public License v2
* `times.nlq` and `daisy.nlq`
  - distributed with Roy Goldman's Daisy-Dot III
  - in the public domain
* `big1.nlq` and `big1.nl1`
  - https://archive.org/details/a8b_abbuc_353_b
  - distributed with FONTSPLIT.MAC by John McGowan
  - in the public domain  
* `cmbx10.120pk`
  - https://www.ctan.org/pkg/cm
  - unmodified bitmap of the Computer Modern font created by Donald Knuth
  - released under his usual licence: https://ctan.org/license/knuth
* `SHILLING.cvt.gz`
  - https://www.commodore.ca/manuals/funet/cbm/geos/graphics/fonts/unsorted/
  - Symbol font created by Dick Estel - copyright 1989 - released for free use
* `Alpha-2B.pdb`
  - http://www.rainerzenz.de/palm/alphafonts.html
  - © 2000/2001 for Alpha Font Collection: Rainer Zenz. If you want to substitute one of
    these fonts to shareware or commercial software, please contact me. For freeware
    it's free, of course. If you want to publish it - do it! But have a look at
    PalmGear for the latest version.
* `WARPSANS.FON`
  - http://www.altsan.org
  - The WarpSans Extended Sizes may be freely used, redistributed, and/or
    modified, by any individual, group or organization, for any purpose.  
    (C) 2013 Alexander Taylor
* `hershey-az.jhf`
  - first 26 lines of `hersh.oc1` from Peter Holzmann's USENET distribution of the Hershey fonts
  - see e.g. https://www.galleyrack.com/hershey/additional-fonts-for-VARKON/hershey/index.html
  - The Hershey Fonts were originally created by Dr. A. V. Hershey
  - See README for conditions
* Terminus Font, `ter-i12n.wsf` and `ter-u28.fnt`
  - Copyright (c) 2019 Dimitar Toshkov Zhekov
    Terminus Font is licensed under the SIL Open Font License, Version 1.1
  - wsfont conversion at https://ftp.netbsd.org/pub/NetBSD/NetBSD-current/src/share/wscons/fonts/ter-112n.wsf.uue
  - vtfont conversion at https://github.com/LionyxML/freebsd-terminus/
* UNSCII 2.1, `unscii-16.hex`
  - https://github.com/viznut/unscii
  - Licensing: You can consider it Public Domain (or CC-0) except for the files
    derived from or containing parts of Roman Czyborra's Unifont project
    (`unifont.hex`, `hex2bdf.pl`, `unscii-16-full.*`) which fall under GPL.
* Spleen Font, `spleen5x8.h`
  - https://github.com/NetBSD/src/blob/trunk/sys/dev/wsfont/spleen5x8.h
  - Copyright (c) 2018-2021 Frederic Cambus <fcambus@openbsd.org>
  - BSD 2-clause licence
* Free Sans `FreeSans9pt7b.h` - GNU FreeFont
  - Original font https://www.gnu.org/software/freefont
  - GNU General Public licence v3, with font exception
  - Header file https://github.com/adafruit/Adafruit-GFX-Library/
  - Copyright (c) 2012 Adafruit Industries.  All rights reserved.
  - BSD 2-clause licence
* Gallant `gallant12x22.h`
  - https://github.com/NetBSD/src/blob/trunk/sys/dev/wsfont/gallant12x22.h
  - Copyright (c) 1992, 1993
    The Regents of the University of California.  All rights reserved.
  - BSD 3-clause licence


### Derivatives of `4x6`

* `4x6.yaff`, `4x6.fzx` were created from `4x6.bdf` using `monobit`
* `4x6.c`, `4x6.c`, `4x6.iigs`, `4x6.sfp`, `4x6*.raw` were created from `4x6.yaff` using `monobit`
* `4x6.dfont` and `4x6.bin` were created from `4x6.bdf` using `ufond` (part of `fondu`)
* `8x8.bbc`, `4x6.vfont*`, `4x6-ams.com`, `4x6.txt`, `4x6.wyse`, `4x6.wof` were created from `4x6.psf` using `psftools` v1.1.1
* `4x6.ttf` was created from `4x6.bdf` using `fonttosfnt`
* `4x6.otb`, `4x6.sfnt.dfont` and `4x6.ffms.ttf` were created from `4x6.bdf` using FontForge
* `4x6.clt` was created from `4x6.bdf` using `vfontas`
* `4x6.mgtk` was created by Kelvin Sherlock
* `4x6*.pcf` were created from `4x6.bdf` using `bdftopcf`
* `4x6.ihex` were created from `4x6.raw` using `srec_cat` (part of `srecord`)
* `4x6.pil` and `4x6.pbm` were created from `4x6.bdf` using `pillow`
* `8x16.hex` was created from `4x6.yaff` using `bittermelon`
* `8x16.draw` was created from `8x16.hex` using `hexdraw`
* `8x16-*.cpi` were created from `8x16.hex` through a PSF intermediate using `monobit` and `psftools`
* `8x16.cp` was extracted from `8x16.cpi` using `codepage -a` and `tail -c 8257`
* `8x16.f16` was created from `8x16.cp` using `monobit`
* `8X16.XB`, `8X16-FRA.COM` and `8X16-TSR.COM` were created from `8x16.f16` using Fontraption
* `8X16-FE.COM` was created from `8X16-FRA.COM` using `FONTEDIT`
* `8X16-REX.COM` was created from `8X16-FRA.COM` using Font Mania 2.2
* `8x8-letafont.com` was created from `8x16.f16` and a stub Letafont file


### Derivatives of `6x13`

* `6x13.fnt` was extracted from `6x13.fon` using `tail -c +449`
* `6x13.dec` was created from `6x13.fnt` using `monobit`
* `6x13.bmf/6x13-json.fnt` was manually converted from `6x13-xml.fnt`
* the other files in `6x13.bmf` were created with Angelcode BMFont


### Derivatives of WebbySmall:

* `webby-small-kerned.yaff` was created from `WebbySmall.pcf` using `pcf2bdf` and `monobit`
  and manually edited to add some kerning and remove non-ascii glyphs.


### Derivatives of Hershey Fonts:
* `hershey.yaff`, `hershey.svg` and `hershey.fon` were created from `hershey-az.jhf` using `monobit`
