def inquiry_draft(latest=None, current=None):
    lots = [latest] if latest else [current.first, current.second] if current else []
    if not lots:
        return "안녕하세요. 경매 물건에 대해 문의드립니다.\n\n문의할 사항\n"
    details = "\n".join("- " + " · ".join(filter(None, (lot.name, lot.case_label))) for lot in lots)
    return "안녕하세요. 아래 경매 물건의 입찰 조건을 문의드립니다.\n\n" + details + "\n\n문의할 사항\n"
