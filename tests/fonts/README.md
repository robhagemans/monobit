The _Fixed 4x6_ and _Fixed 6x13_ fonts used for these tests are in the public domain.
The _WebbySmall_ font was released under an MIT licence.

Source Fonts:

* `4x6.bdf` https://www.cl.cam.ac.uk/~mgk25/ucs-fonts.html
* `6x13.fon` https://www.chiark.greenend.org.uk/~sgtatham/fonts/
* `WebbySmall.fon` and `WebbySmall.pcf` https://github.com/bluescan/proggyfonts/tree/master/ProggyOriginal

Derivative Fonts:

* `4x6.yaff` was created from `4x6.bdf` using `monobit`
* `4x6.psf` was created from `4x6.yaff` using `monobit`
* `4x6.fzx` was created from `4x6.bdf` using `monobit`
* `4x6.c` was created from `4x6.yaff` using `monobit`
* `8x16.hex` was created from `4x6.yaff` using `bittermelon`
* `8x16.draw` was created from `8x16.hex` using `hexdraw`
* `6x13.fnt` was extracted from `6x13.fon` using `tail -c +449`
* `6x13.dec` was created from `6x13.fnt` using `monobit`
* `6x13.bmf/6x13-json.fnt` was manually converted from `6x13-xml.fnt`
* the other files in `6x13.bmf` were created with Angelcode BMFont
* `8x16-*.cpi` were created from `8x16.hex` through a PSF intermediate using `monobit` and `psftools`
* `8x16.cp` was extracted from `8x16.cpi` using `codepage -a` and `tail -c 8257`
* `webby-small-kerned.yaff` was created from `WebbySmall.bdf` (itself created with `pcf2bdf`)
  and manually edited to add some kerning and remove non-ascii glyphs.
