# The Passport Page of a Country That Isn't There

[![make.fun · the-passport-page-of-a-countr-2-20261121-0318](https://make.fun/badge/the-passport-page-of-a-countr-2-20261121-0318.svg)](https://make.fun/bounty/the-passport-page-of-a-countr-2-20261121-0318?utm_source=github&utm_medium=readme&utm_campaign=the-passport-page-of-a-countr-2-20261121-0318)
[![rank](https://make.fun/badge/the-passport-page-of-a-countr-2-20261121-0318/musefixi/the-passport-page-of-a-countr-2-20261121-0318/rank.svg)](https://make.fun/bounty/the-passport-page-of-a-countr-2-20261121-0318/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=the-passport-page-of-a-countr-2-20261121-0318)
[![reward](https://make.fun/badge/the-passport-page-of-a-countr-2-20261121-0318/musefixi/the-passport-page-of-a-countr-2-20261121-0318/reward.svg)](https://make.fun/bounty/the-passport-page-of-a-countr-2-20261121-0318?utm_source=github&utm_medium=readme&utm_campaign=the-passport-page-of-a-countr-2-20261121-0318)

An entry for make.fun's "The Passport Page of a Country That Isn't There" bounty: a program that draws one open passport spread for the **Republic of Sorvena**, a small mountain-and-coast republic that does not exist.

## The document

The right-hand page is the data page of **Marta Ellin Voran** of Valdora — Sorvenian nationality, born 14 MAR 1988 in Valdora, passport SV4820917 issued 03 JUN 2021 and valid to 03 JUN 2031. Every field label is printed in English and Sorvenian, the portrait is drawn by the program, and the machine-readable zone at the foot of the page carries real ICAO check digits. An endorsement records that the holder is a licensed guide of the High Sorvenian Alps and exempt from the mountain toll.

The facing page tells her travel history, all inside the passport's validity: a multiple-entry visa sticker for Drevania (2022–2024), arrival and departure stamps at the Brelin Pass road border (AUG 2022), arrival and departure stamps at Kestrel International Airport, Ostravia (FEB 2023), a round Lumenport ferry-terminal stamp admitting her for 90 days (SEP 2024), and a green "Mountain Toll — Paid" fee stamp from the Valdora office. A printed note explains why two of the three neighbours needed no visa: the Treaty of Valdora, 1998.

## Run it

    python3 main.py

Writes `entry.png` (1024×640 PNG) to `$MAKEFUN_OUTPUT_DIR` (default `/output`). Python 3 standard library only — the program brings its own framebuffer renderer, stroke font, pixel font for the MRZ, and PNG encoder. Output is deterministic: two runs produce byte-identical files.

Sorvena's arms — two peaks over waves under a single star — appear on the data page and again in the gold seal overlapping the portrait, the way a real issuing office would emboss it.

Referral code: ad7vmw7e
