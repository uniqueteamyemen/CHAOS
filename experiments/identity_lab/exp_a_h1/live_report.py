"""Turn the captured live trace into a report. Numbers are computed, prose is the finding."""
from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "results/paylock_live_trace.jsonl"
OUT = ROOT / "results/paylock_live_report.md"


def main() -> None:
    steps = [json.loads(line) for line in TRACE.read_text().splitlines() if line.strip()]
    by_action = {s["action"]: s for s in steps}
    h1 = {s["body"].get("h1") for s in steps if isinstance(s["body"], dict) and s["body"].get("h1")}
    deterministic = len(h1) == 1
    codes = {}
    for s in steps:
        codes[s["code"]] = codes.get(s["code"], 0) + 1

    lines = [
        "# تشغيل حقيقي: باي لوك على جهازي",
        "",
        "`platform.js` **بلا تعديل** من `paylock-core` (HEAD، قراءة فقط). شُغّل محليًا في وضع",
        "الذاكرة المدمج (`REDIS_URL` غائب)، والنسخة المنشورة على Railway لم تعد موجودة",
        "(`404 Application not found`)، فلم يكن هناك طريق آخر لأخذ سجل.",
        "",
        f"**{len(steps)} خطوة**، كل واحدة بختم زمني UTC بالميلي ثانية، ومعرّف الجلسة، ورمز HTTP، والجسم.",
        "",
        "| # | action | code |",
        "|---|---|---|",
    ]
    lines += [f"| {s['step']} | `{s['action']}` | {s['code']} |" for s in steps]
    lines += [
        "",
        f"توزيع الرموز: {', '.join(f'{c}×{n}' for c, n in sorted(codes.items()))}.",
        "",
        "## ما أثبته التشغيل",
        "",
        f"1. **H1 حتمي**: القيمة نفسها صدرت ثلاث مرات — عند الفتح، وعند الحل، وعند الحل مرة أخرى. "
        f"عدد القيم المختلفة في السجل كله: **{len(h1)}**. فالحل ليس إصدارًا ثانيًا، بل قراءة للأول.",
        "2. **البوابة على H1 لا على الفتح.** فتح جلسة بلا `provider_ack` يرجع **200 `UNLOCKED`** "
        "وبلا `h1`، ثم يرفض `/v1/resolve` بـ400. أي أن `UNLOCKED` ليست تصريحًا، بل حالة انتقال؛ "
        "والتصريح هو `EXECUTION_PROVEN` مع `h1`. هذا فرق يُسقط أي عميل يعتبر `UNLOCKED` إذنًا.",
        "3. **حماية التكرار على طبقتين، بسلوكين مختلفين**: إعادة الفتح ترجع **409** (`user_unlock already recorded`)، "
        "بينما إعادة الحل ترجع **200** بالقيمة نفسها. الأولى منع، والثانية تسوية — وكلاهما صحيح، "
        "لكن من يقرأ الرمزين على أنهما متكافئان يفهم النظام خطأً.",
        "4. **`receipt_id` ليس دليلًا، بل مفتاح منع ازدواج تجاري**: جلسة بلا إيصال فُتحت وأُثبتت بنجاح. "
        "وجود الإيصال يمنع تكرار المعاملة (409)، ولا يدخل في شرط H1.",
        "5. **شرط H1 هو إشارتان معًا**: `provider_ack` و`user_unlock`. الرفض يسمّي الناقص صراحةً "
        "(`missing: {provider_ack, user_unlock}`)، وهذا أفضل ما في التصميم: كل رفض منسوب.",
        "6. **الإلغاء يغلق المسارين**: فتح وحل بعد الإلغاء → 409 `Session is closed`.",
        "",
        "## تصحيح لاستنتاجي السابق",
        "",
        "قلت في `h1_corpus_matrix.md` إن I4 «مفتاح نسخة»، وإن الـack معلوماتي في حزمة الأدلة وشرط في Stripe. "
        "الكود يقول غير ذلك: `provider_ack` **شرط دائم** لإصدار H1، و«المعلوماتي» في حزمة 22 أغسطس "
        "يصف **webhook الدفع**، لا الإقرار. فما ظننته تناقضًا بين نسختين هو خلط بين مسمّيين. "
        "القراءة الحقيقية للكود أنهت النقاش الذي كان التجرّد البوليني يدور حوله.",
        "",
        "## ما لا يزال ناقصًا — وهو ناقص فعلًا",
        "",
        "- **التزامن**: وضع الذاكرة أحادي العملية. اختبار «عاصفة إعادة المحاولة» يحتاج Redis وعدة عمليات، "
        "ولم يُجرَ هنا. الحماية موجودة في الكود (`SET NX`، `h1:` مرة واحدة)، لكنها غير مُختبرة تحت تزامن حقيقي.",
        "- **النقل الحقيقي**: لا شبكة، لا Stripe، لا Medusa. هذا سجل للبروتوكول، لا للتكامل.",
        "- **الافتراضات الأمنية**: `PLATFORM_SECRET` و`API_KEY` من متغيرات البيئة، والوضع الافتراضي "
        "هو الذاكرة عند غياب Redis — وهذا يعني أن أي نشر بلا `REDIS_URL` يفقد كل الجلسات عند إعادة التشغيل.",
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"steps": len(steps), "distinct_h1": len(h1), "deterministic": deterministic,
                      "codes": codes}, ensure_ascii=False))


if __name__ == "__main__":
    main()
