
International Components for Unicode
------------------------------------

https://github.com/unicode-org/icu/blob/main/icu4c/source/data/mappings/

>This is the repository for the International Components for Unicode. The ICU project is under the stewardship of The Unicode Consortium.

https://github.com/unicode-org/icu-data/

> This is an auxiliary repository for the International Components for Unicode.
> Main repo: https://github.com/unicode-org/icu
> The ICU project is under the stewardship of The Unicode Consortium.


Notes on CNS11643
-----------------

- The CNS11643 mapping found here is an old one from ICU-3.13, still found at:
  https://opensource.apple.com/source/ICU/ICU-3.13/icuSources/data/mappings/cns-11643-1992.ucm
  and linked on the Wikipedia page https://en.wikipedia.org/wiki/CNS_11643 .
- The current version at the ICU4c mappings repo only includes plane 1 and 2. I have confirmed it is a subset of the one found here.
- There is a version with planes 1-7 at the ICU-data repo https://github.com/unicode-org/icu-data/tree/main/charset/data/ucm .
  The old version given here additionally provides a plane 9, which according to the Wikipedia author *should* be plane 15.

