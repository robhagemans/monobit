MULE charsets from GNU emacs
============================

These character sets are used in Multilingual Emacs. They can be found at https://github.com/emacs-mirror/emacs/tree/master/admin/charsets/mapfiles

Names and aliases are given at https://www.xemacs.org/Documentation/21.5/html/lispref_64.html, from which the below quotes.

> ### 63.2.4 Predefined Charsets
>
> The following charsets are predefined in the C code.
>
>     Name                    Type  Fi Gr Dir Registry
>     --------------------------------------------------------------
>     ascii                    94    B  0  l2r ISO8859-1
>     control-1                94       0  l2r ---
>     latin-iso8859-1          94    A  1  l2r ISO8859-1
>     latin-iso8859-2          96    B  1  l2r ISO8859-2
>     latin-iso8859-3          96    C  1  l2r ISO8859-3
>     latin-iso8859-4          96    D  1  l2r ISO8859-4
>     cyrillic-iso8859-5       96    L  1  l2r ISO8859-5
>     arabic-iso8859-6         96    G  1  r2l ISO8859-6
>     greek-iso8859-7          96    F  1  l2r ISO8859-7
>     hebrew-iso8859-8         96    H  1  r2l ISO8859-8
>     latin-iso8859-9          96    M  1  l2r ISO8859-9
>     thai-tis620              96    T  1  l2r TIS620
>     katakana-jisx0201        94    I  1  l2r JISX0201.1976
>     latin-jisx0201           94    J  0  l2r JISX0201.1976
>     japanese-jisx0208-1978   94x94 @  0  l2r JISX0208.1978
>     japanese-jisx0208        94x94 B  0  l2r JISX0208.19(83|90)
>     japanese-jisx0212        94x94 D  0  l2r JISX0212
>     chinese-gb2312           94x94 A  0  l2r GB2312
>     chinese-cns11643-1       94x94 G  0  l2r CNS11643.1
>     chinese-cns11643-2       94x94 H  0  l2r CNS11643.2
>     chinese-big5-1           94x94 0  0  l2r Big5
>     chinese-big5-2           94x94 1  0  l2r Big5
>     korean-ksc5601           94x94 C  0  l2r KSC5601
>     composite                96x96    0  l2r ---
>
> The following charsets are predefined in the Lisp code.
>
>     Name                     Type  Fi Gr Dir Registry
>     --------------------------------------------------------------
>     arabic-digit             94    2  0  l2r MuleArabic-0
>     arabic-1-column          94    3  0  r2l MuleArabic-1
>     arabic-2-column          94    4  0  r2l MuleArabic-2
>     sisheng                  94    0  0  l2r sisheng_cwnn\|OMRON_UDC_ZH
>     chinese-cns11643-3       94x94 I  0  l2r CNS11643.1
>     chinese-cns11643-4       94x94 J  0  l2r CNS11643.1
>     chinese-cns11643-5       94x94 K  0  l2r CNS11643.1
>     chinese-cns11643-6       94x94 L  0  l2r CNS11643.1
>     chinese-cns11643-7       94x94 M  0  l2r CNS11643.1
>     ethiopic                 94x94 2  0  l2r Ethio
>     ascii-r2l                94    B  0  r2l ISO8859-1
>     ipa                      96    0  1  l2r MuleIPA
>     vietnamese-viscii-lower  96    1  1  l2r VISCII1.1
>     vietnamese-viscii-upper  96    2  1  l2r VISCII1.1
