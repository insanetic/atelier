---
type: llm
weight: 3
---

The review finds the concrete problems of this file, with evidence (rows, counts or values). There are twelve:
(1) three preamble lines before the header (title, export period, blank);
(2) a `Summe` footer row;
(3) `;` delimiter with a UTF-8 BOM;
(4) German number format with the currency inside the amount (`1.234,50 €`);
(5) an accounting negative `(120,00) €`;
(6) mixed EUR and CHF, so amounts must not be summed across currencies;
(7) Excel serial numbers (like `45905`) among the `Erstellt am` timestamps;
(8) timestamps without a timezone;
(9) postal codes with leading zeros that must stay strings;
(10) status values differing only in case (`Bestätigt`/`bestätigt`/`BESTÄTIGT`);
(11) placeholder NULLs (`-` in E-Mail, `n/a` in Nächte);
(12) one exact duplicate booking (B-1017).
Pass if it names at least ten of the twelve. Fail if it states problems the file does not have.
