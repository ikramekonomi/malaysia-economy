# Blind verifier: LKAN audit inventory, links and gap_audit_recurrence (2026-11-06)

The verifier was an independent agent, blind to `lkan_inventory.py`, `lkan_toc.py` and `build_records.py`. It
read the contents pages itself, for 45+ volumes, and opened 12 PDFs. Its full working is in the session scratchpad.

**Verdict: not publishable yet.**

## What is right

* The arithmetic is right. Recurrence, years, n_audits and record ids re-derive exactly.
* Every name_exact_official link obeys its name/year rule.
* State geo codes are right, and the contents-page text equals the PDFs line for line.
* No personal names appear, and no person is linked.
* Clean volumes:
  * federal: CMD.53.2023, CMD.8.2024, CMD.5.2025, CMD.7.2019, CMD.31.2018, CMD.30.2017;
  * state: most 2018-2024 volumes in the chapter layout.

## What is wrong

Precision is 0.87, recall 0.94, and only 54% of sampled rows have body, topic and page all right.

1. **Wrong links.** CMD.30.2017's EC725 helicopter-base audit (KEMENTERIAN PERTAHANAN / JKR) was linked to
   KPWKM, because the row inherited the previous entry's body. CMD.6.2016's 'Pendahuluan' row was linked to JPM.
2. **About 8% of rows are not audits.** They come from:
   * financial-statement chapters (CMD.29.2017, CMD.6.2018, CMD.30.2018, CMD.46.2019);
   * digest and infographic entries (RINGKASAN KESELURUHAN, PENERANGAN INFOGRAFIK);
   * PENUTUP rows;
   * sub-sections of the e-SelfAudit chapter;
   * Tindakan Susulan rows.
3. **Fields are misaligned** in multi-line or bare-page layouts:
   * bodies shift by one entry (CMD.6.2016: 3 of 26 rows right; CMD.16.2021: 5 of 16; CMD.4.2022: 2 of 10);
   * page footers and PENUTUP are glued into topics;
   * part fragments appear as bodies (NEGERI SABAH, BADAN-BADAN BERKANUN PERSEKUTUAN);
   * in the LKAN 1/2026 state volumes, pages are "3" or blank.
4. **Audits are missing:**
   * the e-SelfAudit chapter in 14 volumes;
   * i2M Ventures (CMD.9.2024), JPN (CMD.16.2021), Hospital ATM (CMD.20.2022), MOF concession vehicles
     (CMD.14.2025);
   * the 9 LKAN 2021 Siri 2 state volumes, whose contents page has a broken font encoding and needs OCR;
   * the 2014-2016 image contents pages, of which OCR gave few audits.
5. **Wrong year for 9 records.** The manifest titles of 4 LKAN 1/2026 state volumes say 'TAHUN 2022'; their
   covers do not.
6. **Topic families are matched on title plus agency name, not the title alone as declared.** This gives 119
   assignments from agency names: 'Keretapi Tanah Melayu' gives `land_resources`. Also, the pattern
   'kumpanan wang' should be 'kumpulan wang'.
7. **Entities.** Kementerian Kewangan is absent from entity_name.csv (about 51 MOF audits can never link), and the
   higher-education ministry is split across three entity ids.

## What was done

`build_records.py` sets every link built on the inventory to publishable=false, and every
`gap_audit_recurrence` row carries `verification` = draft, until a re-verification passes. That covers the 143
exact-name links and the 60 owner-signed ones. The owner's signatures are kept in `meta/link_signoff.csv` and
will apply again when the inventory is fixed.

The fixes, in order, are in `HANDOVER.md` (Phase 4):
1. read the TW / bare-page layouts and keep a body to its own entry;
2. drop the non-audit chapters and digest rows;
3. strip footers;
4. OCR the 2021 Siri 2 and 2014-2016 contents pages;
5. correct the 1/2026 years;
6. classify on the title alone (and fix the typo);
7. add MOF to the entity register;
8. verify again.
