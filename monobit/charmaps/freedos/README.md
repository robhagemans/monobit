FreeDOS code pages
==================

This directory contains Unicode mappings for the code pages as used in Henrique Peron's
CPIDOS package https://gitlab.com/FDOS/base/cpidos/, which provides
the code page mapped fonts for FreeDOS.

I originally created these mappings for use with PC-BASIC https://pc-basic.org/. Please report
any issues you may find with these mappings here at https://github.com/robhagemans/monobit/issues.

> Insofar as these mappings are considered a copyrightable work, to the extent possible under law,
> I waive all copyright and related or neighbouring rights to that work under the
> [Creative Commons Zero dedication](http://creativecommons.org/publicdomain/zero/1.0/).
>
> Rob Hagemans 2021-10-09

The list of code pages below is from `CODEPAGE.TXT` in the CPIDOS documentation.


    CPX PACK - LIST OF CPX FILES AND THEIR CODEPAGES
    ================================================

    EGA
    ---

    437 - United States
    850 - Latin-1 (Western European)
    852 - Latin-2 (Central European) (2)
    853 - Latin-3 (Southern European)
    857 - Latin-5 (2)(3)
    858 - Latin-1 with Euro (1)

    1) Provides the Euro sign
       instead of the small dotless "i".
    2) This version follows IBM(c) standards,
       i.e. it provides the Euro sign
       in a codepoint which is left blank
       on their respective MS-DOS(c) versions.
    3) Based upon cp850, trading icelandic for
       turkish letters.



    EGA2
    ----

     775 - Latin-7 (Baltic Rim)
     859 - Latin-9
    1116 - Estonian
    1117 - Latvian
    1118 - Lithuanian (*)
    1119 - Cyrillic Russian and Lithuanian (*)

    * IBM(c) codepage 1118 is identical to codepage 774.
    * IBM(c) codepage 1119 is identical to codepage 772.



    EGA3
    ----

    771 - Cyrillic Russian and Lithuanian (KBL)
    772 - Cyrillic Russian and Lithuanian (**)
    808 - Cyrillic Russian with Euro (*)
    855 - Cyrillic South Slavic
    866 - Cyrillic Russian
    872 - Cyrillic South Slavic with Euro (*)

    *  The Euro versions provide the Euro sign
       instead of the international currency sign.
    ** Codepage 772 is identical to IBM(c) codepage 1119.



    EGA4
    ----

      848 - Cyrillic Ukrainian with Euro (*)
      849 - Cyrillic Belarusian with Euro (*)
     1125 - Cyrillic Ukrainian
     1131 - Cyrillic Belarusian
     3012 - Cyrillic Russian and Latvian ("RusLat")
    30010 - Cyrillic Gagauz and Moldovan

    * The Euro versions provide the Euro sign
      instead of the international currency sign.



    EGA5
    ----

    113 - Yugoslavian Latin
    737 - Greek-2
    851 - Greek (old codepage)
    852 - Latin-2
    858 - Multilingual Latin-1 with Euro
    869 - Greek (*)



    EGA6
    ----

      899 - Armenian
    30008 - Cyrillic Abkhaz and Ossetian
    58210 - Cyrillic Russian and Azeri
    59829 - Georgian
    60258 - Cyrillic Russian and Latin Azeri
    60853 - Georgian with capital letters



    EGA7
    ----

    30011 - Cyrillic Russian Southern District
    30013 - Cyrillic Volga District - Turkic languages
    30014 - Cyrillic Volga District - Finno-ugric languages
    30017 - Cyrillic Northwestern District
    30018 - Cyrillic Russian and Latin Tatar
    30019 - Cyrillic Russian and Latin Chechen



    EGA8
    ----

    770 - Baltic
    773 - Latin-7 (old standard)
    774 - Lithuanian
    775 - Latin-7
    777 - Accented Lithuanian (old)
    778 - Accented Lithuanian



    EGA9
    ----

    858 - Latin-1 with Euro
    860 - Portuguese
    861 - Icelandic
    863 - Canadian French
    865 - Nordic
    867 - Czech Kamenicky



    EGA10
    -----

      667 - Polish
      668 - Polish (polish letters on cp852 codepoints)
      790 - Polish Mazovia
      852 - Latin-2
      991 - Polish Mazovia with Zloty sign
     3845 - Hungarian



    EGA11
    -----

      858 - Latin-1 with Euro
    30000 - Saami
    30001 - Celtic
    30004 - Greenlandic
    30007 - Latin
    30009 - Romani



    EGA12
    -----

      852 - Latin-2
      858 - Latin-1 with Euro
    30003 - Latin American
    30029 - Mexican
    30030 - Mexican II
    58335 - Kashubian



    EGA13
    -----

      852 - Latin-2
      895 - Czech Kamenicky (*)
    30002 - Cyrillic Tajik
    58152 - Cyrillic Kazakh with Euro
    59234 - Cyrillic Tatar
    62306 - Cyrillic Uzbek

    * Identical to cp867.



    EGA14
    -----

    30006 - Vietnamese
    30012 - Cyrillic Russian Siberian and Far Eastern Districts
    30015 - Cyrillic Khanty
    30016 - Cyrillic Mansi
    30020 - Low saxon and frisian
    30021 - Oceania



    EGA15
    -----

    30023 - Southern Africa
    30024 - Northern and Eastern Africa
    30025 - Western Africa
    30026 - Central Africa
    30027 - Beninese
    30028 - Nigerien



    EGA16
    -----

      858 - Latin-1 with Euro
     3021 - Cyrillic MIK Bulgarian
    30005 - Nigerian
    30022 - Canadian First Nations
    30031 - Latin-4 (Northern European)
    30032 - Latin-6



    EGA17
    -----

      862 - Hebrew
      864 - Arabic
    30034 - Cherokee
    30033 - Crimean Tatar with Hryvnia
    30039 - Cyrillic Ukrainian with Hryvnia
    30040 - Cyrillic Russian with Hryvnia



    EGA18
    -----

      856 - Hebrew II
     3846 - Turkish
     3848 - Brazilian ABICOMP
