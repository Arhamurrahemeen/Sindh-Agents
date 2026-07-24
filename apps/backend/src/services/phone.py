def mask_phone(phone: str | None) -> str:
    # api-contract.md §1.4 example format: "+92 3XX ****172"
    # Widget buyers have no phone (only a wa_id session UUID) — no real number to mask.
    if phone is None:
        return "—"
    return f"+92 {phone[3]}XX ****{phone[-3:]}"
