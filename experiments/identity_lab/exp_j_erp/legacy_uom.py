"""Frozen UoM conversion table used by historical A benchmark adapter."""
CATEGORY = {"unit":"count","dozen":"count","kg":"weight","g":"weight","l":"volume","ml":"volume"}
TO_REF = {"unit":1.0,"dozen":12.0,"kg":1.0,"g":0.001,"l":1.0,"ml":0.001}
def convert(qty, src, dst):
    src, dst = (src or "").lower(), (dst or "").lower()
    if src not in CATEGORY or dst not in CATEGORY:
        return None, f"unknown_uom:{src or '?'}->{dst or '?'}"
    if CATEGORY[src] != CATEGORY[dst]:
        return None, f"uom_category_mismatch:{CATEGORY[src]}->{CATEGORY[dst]}"
    if TO_REF[dst] == 0:
        return None, "zero_factor"
    return qty * TO_REF[src] / TO_REF[dst], "ok"
