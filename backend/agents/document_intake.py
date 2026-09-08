"""Document Intake Agent: inventory, provenance, and document-integrity service."""
from .base import AgentDefinition, ToolDefinition, artifact, citation
from ..services import classify_document, document_metadata, duplicate_or_version_gaps, source_fingerprint
from ..vision import vision_ocr_preflight
PROMPT = """You are the Document Intake Agent. Treat the packet as evidence custody:
inventory every retained record, classify it, preserve supplied page/version values,
calculate a local integrity fingerprint, and identify controlling-document candidates.
The packet includes pre-rendered synthetic PNG/PDF pages. Run the local vision/OCR
preflight on its contact sheet, label its result as derived intake evidence, and keep
the preserved source page/version as authoritative. Do not decide compliance, resolve
conflicts, or infer a missing file from an incomplete statement."""
TOOLS = (
    ToolDefinition("retained_text_reader", "Read source-locked text paired with the rendered document page.", "READ_DOCUMENT", lambda d: d["text"]),
    ToolDefinition("document_classifier", "Classify record type using document-name rules.", "READ_DOCUMENT", classify_document),
    ToolDefinition("version_registry", "Preserve supplied document name, version, and page metadata.", "READ_DOCUMENT", lambda d: (d["name"], d["version"], d["page"])),
    ToolDefinition("source_hasher", "Create a deterministic local integrity fingerprint.", "READ_DOCUMENT", source_fingerprint),
    ToolDefinition("metadata_extractor", "Return a compact citation/provenance record.", "READ_DOCUMENT", document_metadata),
    ToolDefinition("duplicate_detector", "Flag repeated document names for reviewer attention.", "READ_DOCUMENT", duplicate_or_version_gaps),
    ToolDefinition("transaction_associator", "Associate each retained record with the selected transaction before downstream use.", "READ_TRANSACTION", lambda t: [{"transactionId": t["id"], "document": d["name"], "version": d["version"]} for d in t["documents"]]),
    ToolDefinition("vision_ocr_preflight", "Render retained pages and submit the contact sheet to local Qwen vision/OCR.", "READ_DOCUMENT_IMAGE", vision_ocr_preflight),
)
async def run(transaction, _: dict):
    docs = transaction["documents"]; metadata = [TOOLS[4].execute(document) for document in docs]
    controlling = [f"{d['name']} {d['version']}" for d in docs if d.get("controlling")]
    associations = TOOLS[6].execute(transaction)
    vision = await TOOLS[7].execute(transaction)
    vision_detail = f"Vision OCR {vision['status'].lower()}: {vision['summary']}"
    if vision.get("observations"): vision_detail += f" Observations: {'; '.join(vision['observations'][:3])}"
    return artifact(f"Inventoried {len(docs)} retained documents with preserved metadata, case association, and a local vision/OCR preflight.", [f"Associated {len(associations)} records with transaction {transaction['id']}.", f"Controlling candidates: {', '.join(controlling) or 'none flagged'}", f"Classifications: {', '.join(sorted(set(item['classification'] for item in metadata)))}", *TOOLS[5].execute(docs), vision_detail, "Vision output is a derived intake aid; retained source text and page citations remain authoritative."], [citation(d) for d in docs], "Pass inventory, provenance metadata, and vision observations to Evidence Agent.", inventory=metadata, associations=associations, visionOcr=vision)
DEFINITION = AgentDefinition("document-intake-agent", "Document Intake Agent", "Creates a provenance-preserving inventory, fingerprints retained records, and runs a cached local Qwen vision/OCR preflight against synthetic document-page images.", PROMPT, ("Inventory documents", "Preserve provenance", "Classify records", "Detect metadata gaps", "Run local vision OCR preflight"), TOOLS, run)
