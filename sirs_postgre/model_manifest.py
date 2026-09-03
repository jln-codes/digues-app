"""Extraction déterministe du modèle historique SIRS depuis le snapshot Ecore."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REFERENCE_DIR = Path("docs/reference/sirs-2.55")
DEFAULT_ECORE_PATH = DEFAULT_REFERENCE_DIR / "sirs.ecore"
DEFAULT_LABELS_PATH = DEFAULT_REFERENCE_DIR / "labels"
DEFAULT_MANIFEST_PATH = DEFAULT_REFERENCE_DIR / "sirs_model_manifest.json"

XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"


@dataclass(frozen=True)
class EcoreField:
    name: str
    kind: str
    type: str | None
    raw_type: str | None
    declared_in: str
    lower_bound: int
    upper_bound: int
    upper_bound_raw: str
    many: bool
    containment: bool | None
    opposite: str | None
    default_value: str | None
    annotations: tuple[dict[str, object], ...]
    label: str | None = None

    def for_class(self, class_name: str) -> dict[str, object]:
        return {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "type": self.type,
            "raw_type": self.raw_type,
            "declared_in": self.declared_in,
            "inherited": self.declared_in != class_name,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "upper_bound_raw": self.upper_bound_raw,
            "many": self.many,
            "containment": self.containment,
            "opposite": self.opposite,
            "default_value": self.default_value,
            "annotations": list(self.annotations),
        }


@dataclass(frozen=True)
class EcoreClass:
    name: str
    super_types: tuple[str, ...]
    couchdb_document: bool
    annotations: tuple[dict[str, object], ...]
    declared_fields: tuple[EcoreField, ...]
    class_labels: dict[str, str]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _type_name(raw_type: str | None) -> str | None:
    if not raw_type:
        return None
    if "#//" in raw_type:
        return raw_type.rsplit("#//", 1)[-1]
    return raw_type.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def _parse_super_types(raw_super_types: str | None) -> tuple[str, ...]:
    if not raw_super_types:
        return ()
    return tuple(
        item.rsplit("#//", 1)[-1]
        for item in raw_super_types.split()
        if item.strip()
    )


def _parse_annotations(element: ElementTree.Element) -> tuple[dict[str, object], ...]:
    annotations: list[dict[str, object]] = []
    for child in element:
        if _strip_namespace(child.tag) != "eAnnotations":
            continue
        details = {
            detail.attrib.get("key"): detail.attrib.get("value", "")
            for detail in child
            if _strip_namespace(detail.tag) == "details"
            and detail.attrib.get("key") is not None
        }
        annotations.append(
            {
                "source": child.attrib.get("source"),
                "details": dict(sorted(details.items())),
            }
        )
    return tuple(annotations)


def _couchdb_document(annotations: tuple[dict[str, object], ...]) -> bool:
    for annotation in annotations:
        if annotation.get("source") != "couchDBDocument":
            continue
        details = annotation.get("details")
        if isinstance(details, dict) and "document" in details:
            return str(details["document"]).lower() == "true"
        return True
    return False


def _unescape_java_property(value: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char != "\\" or index + 1 >= len(value):
            result.append(char)
            index += 1
            continue
        escaped = value[index + 1]
        if escaped == "u" and index + 5 < len(value):
            codepoint = value[index + 2 : index + 6]
            try:
                result.append(chr(int(codepoint, 16)))
                index += 6
                continue
            except ValueError:
                pass
        replacements = {
            "t": "\t",
            "n": "\n",
            "r": "\r",
            "f": "\f",
        }
        result.append(replacements.get(escaped, escaped))
        index += 2
    return "".join(result)


def _ends_with_continuation(line: str) -> bool:
    backslashes = 0
    for char in reversed(line):
        if char != "\\":
            break
        backslashes += 1
    return backslashes % 2 == 1


def _split_property(line: str) -> tuple[str, str]:
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char in "=:" or char.isspace():
            key = line[:index].rstrip()
            remainder = line[index:]
            remainder = remainder.lstrip()
            if remainder[:1] in ("=", ":"):
                remainder = remainder[1:].lstrip()
            return key, remainder
    return line, ""


def load_labels(labels_path: Path) -> dict[str, dict[str, str]]:
    if not labels_path.is_dir():
        raise FileNotFoundError(f"Répertoire de libellés absent : {labels_path}")
    labels: dict[str, dict[str, str]] = {}
    for path in sorted(labels_path.glob("*.properties")):
        entries: dict[str, str] = {}
        logical_lines: list[str] = []
        pending = ""
        for raw_line in path.read_text(encoding="iso-8859-1").splitlines():
            line = raw_line.lstrip()
            if not pending and (not line or line.startswith(("#", "!"))):
                continue
            if pending:
                pending += line
            else:
                pending = line
            if _ends_with_continuation(pending):
                pending = pending[:-1]
                continue
            logical_lines.append(pending)
            pending = ""
        if pending:
            logical_lines.append(pending)
        for line in logical_lines:
            key, value = _split_property(line)
            if key:
                entries[_unescape_java_property(key)] = _unescape_java_property(value)
        labels[path.stem] = entries
    return labels


def parse_ecore(ecore_path: Path, labels_path: Path) -> dict[str, EcoreClass]:
    if not ecore_path.is_file():
        raise FileNotFoundError(f"Snapshot Ecore absent : {ecore_path}")
    labels = load_labels(labels_path)
    root = ElementTree.parse(ecore_path).getroot()
    classes: dict[str, EcoreClass] = {}
    for classifier in root.findall("eClassifiers"):
        if classifier.attrib.get(XSI_TYPE) != "ecore:EClass":
            continue
        class_name = classifier.attrib["name"]
        class_labels = labels.get(class_name, {})
        annotations = _parse_annotations(classifier)
        fields: list[EcoreField] = []
        for feature in classifier.findall("eStructuralFeatures"):
            feature_type = feature.attrib.get(XSI_TYPE)
            if feature_type == "ecore:EAttribute":
                kind = "ATTRIBUTE"
            elif feature_type == "ecore:EReference":
                kind = "REFERENCE"
            else:
                continue
            raw_upper_bound = feature.attrib.get("upperBound", "1")
            upper_bound = int(raw_upper_bound)
            raw_type = feature.attrib.get("eType")
            fields.append(
                EcoreField(
                    name=feature.attrib["name"],
                    kind=kind,
                    type=_type_name(raw_type),
                    raw_type=raw_type,
                    declared_in=class_name,
                    lower_bound=int(feature.attrib.get("lowerBound", "0")),
                    upper_bound=upper_bound,
                    upper_bound_raw=raw_upper_bound,
                    many=upper_bound == -1 or upper_bound > 1,
                    containment=(
                        feature.attrib.get("containment") == "true"
                        if kind == "REFERENCE"
                        else None
                    ),
                    opposite=_type_name(feature.attrib.get("eOpposite")),
                    default_value=feature.attrib.get("defaultValueLiteral"),
                    annotations=_parse_annotations(feature),
                    label=class_labels.get(feature.attrib["name"]),
                )
            )
        classes[class_name] = EcoreClass(
            name=class_name,
            super_types=_parse_super_types(classifier.attrib.get("eSuperTypes")),
            couchdb_document=_couchdb_document(annotations),
            annotations=annotations,
            declared_fields=tuple(fields),
            class_labels={
                key: class_labels[key]
                for key in ("class", "classPlural", "classAbrege")
                if key in class_labels
            },
        )
    return classes


def resolve_effective_fields(
    class_name: str,
    classes: dict[str, EcoreClass],
    stack: tuple[str, ...] = (),
) -> tuple[EcoreField, ...]:
    if class_name in stack:
        cycle = " -> ".join((*stack, class_name))
        raise ValueError(f"Cycle d'héritage Ecore détecté : {cycle}")
    ecore_class = classes[class_name]
    fields: list[EcoreField] = []
    seen: set[str] = set()
    for super_type in ecore_class.super_types:
        if super_type not in classes:
            continue
        for field in resolve_effective_fields(super_type, classes, (*stack, class_name)):
            if field.name not in seen:
                fields.append(field)
                seen.add(field.name)
    for field in ecore_class.declared_fields:
        if field.name not in seen:
            fields.append(field)
            seen.add(field.name)
    return tuple(fields)


def build_manifest(
    *,
    ecore_path: Path = DEFAULT_ECORE_PATH,
    labels_path: Path = DEFAULT_LABELS_PATH,
) -> dict[str, object]:
    classes = parse_ecore(ecore_path, labels_path)
    class_entries: dict[str, object] = {}
    for class_name in sorted(classes):
        ecore_class = classes[class_name]
        class_entries[class_name] = {
            "name": ecore_class.name,
            "label": ecore_class.class_labels.get("class"),
            "class_labels": ecore_class.class_labels,
            "super_types": list(ecore_class.super_types),
            "couchdb_document": ecore_class.couchdb_document,
            "annotations": list(ecore_class.annotations),
            "declared_fields": [
                field.for_class(class_name) for field in ecore_class.declared_fields
            ],
            "effective_fields": [
                field.for_class(class_name)
                for field in resolve_effective_fields(class_name, classes)
            ],
        }
    return {
        "model_version": "2.55",
        "source": {
            "ecore": ecore_path.as_posix(),
            "ecore_sha256": sha256_file(ecore_path),
            "labels": labels_path.as_posix(),
        },
        "generator": {
            "plugin": "fr.sirs.maven:gen-maven-plugin",
            "goals": ["fxmodel", "fxmodel2sql"],
            "model": "model/sirs.ecore",
            "model_package": "fr.sirs.core.model",
        },
        "summary": {
            "class_count": len(class_entries),
            "couchdb_document_class_count": sum(
                1
                for ecore_class in classes.values()
                if ecore_class.couchdb_document
            ),
        },
        "classes": class_entries,
    }


def write_manifest(
    output_path: Path = DEFAULT_MANIFEST_PATH,
    *,
    ecore_path: Path = DEFAULT_ECORE_PATH,
    labels_path: Path = DEFAULT_LABELS_PATH,
) -> dict[str, object]:
    manifest = build_manifest(ecore_path=ecore_path, labels_path=labels_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
