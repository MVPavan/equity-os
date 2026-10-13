"""Lossless lexical dimensions plus independently resolved QName identity."""

from typing import Any

from lxml import etree  # type: ignore[import-untyped]

XBRLDI = "{http://xbrl.org/2006/xbrldi}"


def collect_dimensions(container: Any) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Keep filed aliases and resolve axis/member namespaces at the declaring element."""
    lexical: list[tuple[str, str]] = []
    resolved: list[tuple[str, str]] = []
    if container is None:
        return lexical, resolved
    for kind in ("explicitMember", "typedMember"):
        for member in container.findall(f"{XBRLDI}{kind}"):
            axis = member.get("dimension")
            if axis is None:
                raise ValueError(f"dimension {kind} has no axis")
            if kind == "explicitMember":
                value = (member.text or "").strip()
                identity = _expanded(member, value)
            else:
                inner = "".join(part.strip() for part in member.itertext() if part.strip())
                value = f"typed:{inner}"
                identity = f"typed:{','.join(str(child.tag) for child in member)}:{inner}"
            lexical.append((axis, value))
            resolved.append((_expanded(member, axis), identity))
    return lexical, resolved


def _expanded(element: Any, text: str) -> str:
    """The URI/local identity of a lexical QName; an unbound name is malformed evidence."""
    prefix, _, local = text.rpartition(":")
    namespace = element.nsmap.get(prefix or None)
    if not namespace or not local:
        raise ValueError(f"dimension QName {text!r} has no bound namespace/local name")
    return str(etree.QName(namespace, local))
