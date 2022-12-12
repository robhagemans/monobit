## Testing fonts

The fonts are included here for testing and some have been modified. If you wish to use these fonts
for other purposes, it is recommended that you download them from the original source, not from here.

Original sources:
* `4x6.bdf`
  - https://www.cl.cam.ac.uk/~mgk25/ucs-fonts.html
  - in the public domain
* `6x13.fon`
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


### Derivatives of `4x6`

* `4x6.yaff` was created from `4x6.bdf` using `monobit`
* `4x6.psf` was created from `4x6.yaff` using `monobit`
* `4x6.fzx` was created from `4x6.bdf` using `monobit`
* `4x6.c` was created from `4x6.yaff` using `monobit`
* `4x6.dfont` was created from `4x6.bdf` using `ufond` (part of `fondu`)
* `4x6.vfont?e` were created from `4x6.psf` using `psftools-1.1.1`
* `8x16.hex` was created from `4x6.yaff` using `bittermelon`
* `8x16.draw` was created from `8x16.hex` using `hexdraw`
* `8x16-*.cpi` were created from `8x16.hex` through a PSF intermediate using `monobit` and `psftools`
* `8x16.cp` was extracted from `8x16.cpi` using `codepage -a` and `tail -c 8257`


### Derivatives of `6x13`

* `6x13.fnt` was extracted from `6x13.fon` using `tail -c +449`
* `6x13.dec` was created from `6x13.fnt` using `monobit`
* `6x13.bmf/6x13-json.fnt` was manually converted from `6x13-xml.fnt`
* the other files in `6x13.bmf` were created with Angelcode BMFont


### Derivatives of WebbySmall:

* `webby-small-kerned.yaff` was created from `WebbySmall.pcf` using `pcf2bdf` and `monobit`
  and manually edited to add some kerning and remove non-ascii glyphs.
