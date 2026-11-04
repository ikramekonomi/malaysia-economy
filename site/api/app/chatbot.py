"""Tanya Fiskal: intent classification + parameter extraction only, never SQL generation.

Claude is given one tool per entry in templates.TEMPLATES. It must call exactly one tool
to answer any factual question; the tool's return value (structured data + citations) is
handed back to Claude to phrase into a final answer. Claude never states a number that
didn't come from a tool result.
"""
import json
import os

import anthropic

from .templates import TEMPLATES

MODEL = os.environ.get("FISKAL_CHAT_MODEL", "claude-sonnet-5")

SYSTEM_PROMPT = """Anda ialah Tanya Fiskal, pembantu yang menjawab soalan tentang kewangan \
awam Persekutuan Malaysia menggunakan data dari PKKP (Penyata Kewangan Kerajaan \
Persekutuan, teraudit) dan Tinjauan Fiskal MOF.

PERATURAN KETAT:
1. Anda MESTI memanggil satu tool bagi SETIAP soalan berkaitan fakta fiskal. Jangan \
sekali-kali menyatakan angka daripada ingatan atau anggaran anda sendiri.
2. Jika tiada tool sesuai untuk soalan tersebut, beritahu pengguna dengan jujur bahawa \
anda tidak dapat menjawabnya buat masa ini, dan cadangkan jenis soalan yang boleh anda \
jawab -- JANGAN cuba anggarkan jawapan.
3. Untuk soalan mengenai kementerian, anda MESTI memanggil list_ministries dahulu jika \
anda tidak pasti kod kanun (canonical_code) kementerian tersebut, supaya kod yang betul \
digunakan (kementerian yang dinomborkan semula, cth. Pendidikan B.41->B.63, disatukan).
4. "OPEX"/"perbelanjaan mengurus" dan "DEVEX"/"perbelanjaan pembangunan" pada peringkat \
negara mempunyai DUA asas: kasar (gross, jumlah sebenar teraudit) dan bersih (net, \
mengikut konvensyen Tinjauan Fiskal MOF). Guna angka BERSIH (net) sebagai jawapan utama \
melainkan diminta sebaliknya, tetapi sentiasa sebut kedua-dua angka jika kedua-duanya ada.
4a. DEVEX BERSIH mempunyai DUA penerbit: devex_net_rm (MOF Tinjauan Fiskal, hanya \
FY2015-2024) dan devex_net_bnm_rm (BNM MSB 3.1, FY2009-2024). Guna MOF jika \
ada, BNM jika tidak, dan SENTIASA nyatakan penerbit bagi setiap angka. Untuk siri \
beberapa tahun, guna SATU penerbit sahaja bagi semua tahun (biasanya BNM, kerana \
lengkap) -- jangan campurkan MOF dan BNM dalam satu siri.
5. Bagi perbelanjaan kementerian (ministry_fiscal), HANYA angka kasar (gross) wujud -- \
tiada konsep "bersih" pada peringkat kementerian. Jangan cuba kira anggaran bersih untuk \
satu kementerian.
6. SETIAP jawapan MESTI menyebut sumber (jadual data + asas/basis) daripada citations \
yang dipulangkan oleh tool, dalam ayat ringkas di penghujung jawapan (cth. "Sumber: \
curated.fact_fiscal_headline").
7. Jawab dalam Bahasa Malaysia melainkan pengguna bertanya dalam Bahasa Inggeris.
8. Sertakan RM secara eksplisit dan sebutkan jika angka dalam bilion/juta ringgit."""


def _tool_schema():
    return [
        {
            "name": "national_fiscal_headline",
            "description": "Perbelanjaan mengurus (opex) dan perbelanjaan pembangunan (devex) "
                            "negara, kasar dan bersih, mengikut tahun. Guna untuk soalan tentang "
                            "jumlah keseluruhan negara.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "year_from": {"type": "integer", "description": "Tahun mula (2009-2024)"},
                    "year_to": {"type": "integer", "description": "Tahun akhir (2009-2024)"},
                },
            },
        },
        {
            "name": "list_ministries",
            "description": "Senarai semua kementerian (kod kanun/canonical_code + nama). Panggil "
                            "ini dahulu untuk cari kod yang betul sebelum panggil ministry_fiscal.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "ministry_fiscal",
            "description": "Perbelanjaan KASAR (gross) satu kementerian tertentu mengikut tahun. "
                            "Perlukan canonical_code (dapatkan daripada list_ministries dahulu).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "canonical_code": {"type": "string", "description": "cth. 'B.63' atau 'P.21'"},
                    "year_from": {"type": "integer"},
                    "year_to": {"type": "integer"},
                },
                "required": ["canonical_code"],
            },
        },
        {
            "name": "budget_vs_actual",
            "description": "Belanjawan yang dijadualkan berbanding perbelanjaan sebenar teraudit, "
                            "keseluruhan negara.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "year_from": {"type": "integer"},
                    "year_to": {"type": "integer"},
                    "side": {"type": "string", "enum": ["oe", "de", "total"],
                              "description": "oe=mengurus, de=pembangunan, total=keseluruhan"},
                },
            },
        },
        {
            "name": "obligations_summary",
            "description": "Hutang, PFI, jaminan, komitmen, tunggakan -- liabiliti kerajaan di "
                            "luar akaun tunai biasa.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "year_from": {"type": "integer"},
                    "year_to": {"type": "integer"},
                    "obligation_class": {"type": "string",
                                           "description": "cth. 'hutang', 'jaminan', 'pfi', 'komitmen'"},
                },
            },
        },
        {
            "name": "revenue_headline",
            "description": "Jumlah hasil (revenue) kerajaan persekutuan mengikut tahun.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "year_from": {"type": "integer"},
                    "year_to": {"type": "integer"},
                },
            },
        },
    ]


def answer_question(question: str, max_tool_calls: int = 3) -> dict:
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": question}]
    all_citations = []
    tool_calls_used = 0

    while True:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=_tool_schema(),
            messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})

        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if not tool_uses or tool_calls_used >= max_tool_calls:
            text = "".join(b.text for b in resp.content if b.type == "text")
            return {"answer": text, "citations": all_citations}

        tool_results = []
        for block in tool_uses:
            tool_calls_used += 1
            fn = TEMPLATES.get(block.name)
            if fn is None:
                result = {"error": f"unknown tool {block.name}"}
            else:
                try:
                    result = fn(**block.input)
                    all_citations.extend(result.get("citations", []))
                except Exception as e:
                    result = {"error": str(e)}
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, default=str),
            })
        messages.append({"role": "user", "content": tool_results})
