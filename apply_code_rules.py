"""
apply_code_rules.py

Apply Code Block format ke rules — ek jagah, single source of truth.
Main Window ke "Show Format Rules" button isi text ko chat mein paste
karta hai, taaki naye session mein AI/user ko format yaad dilaya ja sake.
"""

APPLY_CODE_RULES_TEXT = """
📜 **Apply Code — Format Rules**

Ye poora block kisi bhi naye chat session mein AI ko copy-paste kar do — isi format mein code dega, exact syntax ke saath.

---

**1) Naya file banana / poori file replace karna:**

FILE: path/to/file.py
#start#
...poora file content yahan...
#end#

(File exist nahi karti to naya banegi, exist karti hai to poori replace hogi — backup automatic banta hai.)

---

**2) Function/Method replace — sirf naam dekar (chhota, safe, bada function bhi):**

FILE: path/to/file.py
#find#
function_ka_naam
#replace#
def function_ka_naam(...):
    ...poora naya function body...
#end#

Class ke andar method ho to:

FILE: path/to/file.py
#find#
ClassName.method_naam
#replace#
    def method_naam(self, ...):
        ...poora naya method body...
#end#

(System AST se poora purana function/method dhund kar replace karta hai — chahe 3 lines ho ya 300. Sirf .py files ke liye kaam karta hai. #find# mein SIRF naam likhna hai, code nahi.)

---

**3) Chhoti si line/text replace — literal exact match:**

FILE: path/to/file.py
#find#
...exact purana text (file mein jaisa hai waisa hi, whitespace bhi match hona chahiye)...
#replace#
...naya text...
#end#

(Ye text file mein EXACTLY ek hi baar milna chahiye, warna safety ke liye apply nahi hoga.)

---

**Multiple blocks ek saath (mix bhi kar sakte ho):**

FILE: file_a.py
#start#
...naya file...
#end#

FILE: file_b.py
#find#
purana_function_naam
#replace#
def purana_function_naam():
    ...naya code...
#end#

---

**🔒 Safety Rules:**
- Har replace/patch se pehle automatic timestamped backup banta hai (`backups/` folder mein).
- File project-folder ke bahar kabhi nahi likhi ja sakti.
- #find# ka text ambiguous (0 baar ya 1+ baar) mile to apply NAHI hoga — safe fail.
- Koi API call nahi hoti — sab local, zero cost, turant apply.

**Marker keywords case-insensitive hain** — #START#, #Start#, #start# sab chalega.
""".strip()