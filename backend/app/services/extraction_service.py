"""AI-based document extraction service supporting Gemini/OpenAI multimodal models and heuristic parsing."""

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.utils.helpers import parse_numeric


def is_valid_key(key: Optional[str]) -> bool:
    """Checks whether an API key is non-empty and not a dummy placeholder."""
    if not key:
        return False
    k = key.strip()
    return len(k) > 15 and not k.startswith("your_") and "placeholder" not in k.lower()


class ExtractionService:
    """Extracts structured key-value pairs, tables, and evidence from document text and images."""

    @classmethod
    def extract(
        cls,
        document_type: str,
        page_records: List[Dict[str, Any]],
        page_images: List[bytes]
    ) -> Tuple[Dict[str, Any], Optional[float]]:
        """
        Main extraction entry point.
        Attempts LLM extraction if API key is configured; otherwise falls back to intelligent regex parser.
        Returns:
            - extracted_data: Dict[str, Any]
            - overall_confidence: Optional[float]
        """
        doc_type_clean = document_type.lower().strip()
        logger.info(f"Initiating extraction for document_type: '{doc_type_clean}' across {len(page_records)} pages.")

        extracted_data = None
        confidence = None

        gemini_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
        openai_key = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")

        # 1. Try Gemini if valid API key available
        if is_valid_key(gemini_key):
            try:
                extracted_data, confidence = cls._extract_with_gemini(
                    doc_type_clean, page_records, page_images, gemini_key
                )
            except Exception as e:
                logger.warning(f"Gemini extraction failed, falling back to rule-based parser: {e}")

        # 2. Try OpenAI if valid API key available and Gemini not used
        if not extracted_data and is_valid_key(openai_key):
            try:
                extracted_data, confidence = cls._extract_with_openai(
                    doc_type_clean, page_records, openai_key
                )
            except Exception as e:
                logger.warning(f"OpenAI extraction failed, falling back to rule-based parser: {e}")

        # 3. Deterministic / Heuristic fallback parser
        if not extracted_data:
            logger.info("Executing deterministic fallback extractor.")
            extracted_data, confidence = cls._extract_with_heuristics(doc_type_clean, page_records)

        # Calculate overall confidence if not set
        if confidence is None:
            confidence = cls._calculate_confidence(extracted_data)

        return extracted_data, confidence

    # --------------------------------------------------------------------------
    # GEMINI MULTIMODAL EXTRACTION
    # --------------------------------------------------------------------------
    @classmethod
    def _extract_with_gemini(
        cls,
        document_type: str,
        page_records: List[Dict[str, Any]],
        page_images: List[bytes],
        api_key: str
    ) -> Tuple[Dict[str, Any], float]:
        """Calls Gemini Multimodal API via google-genai SDK."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        prompt = cls._get_extraction_prompt(document_type)

        contents: List[Any] = [prompt]
        for img_bytes in page_images:
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0
            )
        )

        res_text = response.text.strip()
        data = json.loads(res_text)
        confidence = cls._calculate_confidence(data)
        return data, confidence

    # --------------------------------------------------------------------------
    # OPENAI EXTRACTION
    # --------------------------------------------------------------------------
    @classmethod
    def _extract_with_openai(
        cls,
        document_type: str,
        page_records: List[Dict[str, Any]],
        api_key: str
    ) -> Tuple[Dict[str, Any], float]:
        """Calls OpenAI API."""
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        prompt = cls._get_extraction_prompt(document_type)
        combined_text = "\n\n".join([f"--- PAGE {p['page_number']} ---\n{p['text']}" for p in page_records])

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a financial document extraction AI that outputs strict JSON."},
                {"role": "user", "content": f"{prompt}\n\nDocument Text:\n{combined_text}"}
            ],
            temperature=0.0
        )

        data = json.loads(completion.choices[0].message.content)
        confidence = cls._calculate_confidence(data)
        return data, confidence

    # --------------------------------------------------------------------------
    # HEURISTIC / REGEX / FALLBACK EXTRACTOR
    # --------------------------------------------------------------------------
    @classmethod
    def _extract_with_heuristics(
        cls,
        document_type: str,
        page_records: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], float]:
        """Robust deterministic text parser when external LLM is not configured."""
        full_text = "\n".join([p.get("text", "") for p in page_records])

        if document_type == "invoice":
            return cls._parse_invoice_heuristics(full_text, page_records)
        elif document_type == "balance_sheet":
            return cls._parse_balance_sheet_heuristics(full_text, page_records)
        elif document_type == "profit_and_loss":
            return cls._parse_pnl_heuristics(full_text, page_records)
        elif document_type == "cash_flow_statement":
            return cls._parse_cash_flow_heuristics(full_text, page_records)
        else:
            return {}, 0.50

    @classmethod
    def _parse_invoice_heuristics(cls, text: str, page_records: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], float]:
        data: Dict[str, Any] = {}

        # 1. Invoice Number
        inv_match = re.search(r"(?i)(?:invoice\s*number|invoice\s*no\.?|invoice\s*#|inv\s*#|inv\s*no\.?)\s*[:#-]?\s*([A-Za-z0-9\-_/]+)", text)
        if not inv_match:
            inv_match = re.search(r"\b(INV[-_][A-Za-z0-9_\-]+)", text, re.IGNORECASE)

        if inv_match:
            val = inv_match.group(1).strip()
            # Guard against run-on text from unspaced PDF stream (e.g. INV-001Date -> INV-001)
            val = re.split(r"(?i)(?:date|bill|to|from|subtotal|tax)", val)[0].strip()
            data["invoice_number"] = {
                "value": val,
                "confidence": 0.98,
                "page_number": 1,
                "evidence": {"source_text": inv_match.group(0), "page_number": 1}
            }
        else:
            data["invoice_number"] = {"value": None, "confidence": 0.0, "page_number": 1}

        # 2. Invoice Date
        date_match = re.search(r"(?i)\b(?:invoice\s*date|date)\s*[:#-]?\s*(\d{4}[-/.]\d{2}[-/.]\d{2}|\d{2}[-/.]\d{2}[-/.]\d{4}|\b[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})", text)
        if date_match:
            val = date_match.group(1).strip()
            data["invoice_date"] = {
                "value": val,
                "confidence": 0.97,
                "page_number": 1,
                "evidence": {"source_text": date_match.group(0), "page_number": 1}
            }
        else:
            data["invoice_date"] = {"value": None, "confidence": 0.0, "page_number": 1}

        # 3. Vendor & Customer Name
        vendor_match = re.search(r"(?i)\b(?:from|vendor|seller|billed\s*by)\s*[:#-]?\s*([^\n\r]+)", text)
        vendor_val = vendor_match.group(1).strip() if vendor_match else None
        if not vendor_val:
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            for l in lines[:4]:
                if not re.search(r"(?i)(invoice|date|bill|subtotal|total)", l):
                    vendor_val = l
                    break

        data["vendor_name"] = {
            "value": vendor_val,
            "confidence": 0.95 if vendor_val else 0.0,
            "page_number": 1,
            "evidence": {"source_text": vendor_val or "", "page_number": 1} if vendor_val else None
        }

        cust_match = re.search(r"(?i)\b(?:bill\s*to|customer|client|sold\s*to)\s*[:#-]?\s*([^\n\r]+)", text)
        cust_val = cust_match.group(1).strip() if cust_match else None
        data["customer_name"] = {
            "value": cust_val,
            "confidence": 0.95 if cust_val else 0.0,
            "page_number": 1,
            "evidence": {"source_text": cust_match.group(0) if cust_match else "", "page_number": 1} if cust_val else None
        }

        # 4. Currency
        curr_match = re.search(r"\b(USD|EUR|GBP|INR|AUD|CAD|SGD|\$|€|£|₹)\b", text)
        curr = curr_match.group(1) if curr_match else "USD"
        if curr == "$": curr = "USD"
        elif curr == "€": curr = "EUR"
        elif curr == "£": curr = "GBP"
        elif curr == "₹": curr = "INR"
        data["currency"] = {"value": curr, "confidence": 0.99, "page_number": 1}

        # 5. Financial Totals (line-bounded matching)
        def find_money(patterns: List[str]) -> Tuple[Optional[float], Optional[str]]:
            for pat in patterns:
                for line in text.splitlines():
                    m = re.search(pat, line, re.IGNORECASE)
                    if m:
                        num = parse_numeric(m.group(1))
                        if num is not None:
                            return num, line.strip()
            return None, None

        sub_val, sub_ev = find_money([
            r"\bsubtotal\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"
        ])
        data["subtotal"] = {
            "value": sub_val,
            "confidence": 0.98 if sub_val is not None else 0.0,
            "page_number": 1,
            "evidence": {"source_text": sub_ev, "page_number": 1} if sub_ev else None
        }

        tax_val, tax_ev = find_money([
            r"\b(?:tax|vat|gst)(?:\s*\([^)]*\))?\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"
        ])
        data["tax_amount"] = {
            "value": tax_val,
            "confidence": 0.96 if tax_val is not None else 0.0,
            "page_number": 1,
            "evidence": {"source_text": tax_ev, "page_number": 1} if tax_ev else None
        }

        disc_val, disc_ev = find_money([
            r"\bdiscount\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"
        ])
        data["discount"] = {
            "value": disc_val if disc_val is not None else 0.0,
            "confidence": 0.95,
            "page_number": 1,
            "evidence": {"source_text": disc_ev, "page_number": 1} if disc_ev else None
        }

        tot_val, tot_ev = find_money([
            r"\b(?:total\s*amount|grand\s*total|total\s*due|amount\s*due)\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)",
            r"^\s*total\s*[:=]\s*([$€£₹A-Z\s]*[\d,.]+)"
        ])
        data["total_amount"] = {
            "value": tot_val,
            "confidence": 0.99 if tot_val is not None else 0.0,
            "page_number": 1,
            "evidence": {"source_text": tot_ev, "page_number": 1} if tot_ev else None
        }

        # 6. Parse Line Items
        data["line_items"] = []
        line_item_regex = re.compile(
            r"([A-Za-z0-9\s\-_]+?)\s+(\d+(?:\.\d+)?)\s+([$€£₹]?[\d,.]+)\s+([$€£₹]?[\d,.]+)"
        )
        for line in text.splitlines():
            line_str = line.strip()
            if any(h in line_str.lower() for h in ["description", "subtotal", "total", "invoice", "date", "bill"]):
                continue
            m = line_item_regex.match(line_str)
            if m:
                desc = m.group(1).strip()
                qty = parse_numeric(m.group(2))
                up = parse_numeric(m.group(3))
                amt = parse_numeric(m.group(4))
                if desc and qty and up and amt:
                    data["line_items"].append({
                        "description": desc,
                        "quantity": qty,
                        "unit_price": up,
                        "amount": amt
                    })

        if not data["line_items"] and (tot_val or sub_val):
            data["line_items"].append({
                "description": "General Services / Goods",
                "quantity": 1.0,
                "unit_price": sub_val or tot_val,
                "amount": sub_val or tot_val
            })

        conf = cls._calculate_confidence(data)
        return data, conf

    @classmethod
    def _parse_balance_sheet_heuristics(cls, text: str, page_records: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], float]:
        data: Dict[str, Any] = {}

        def find_money(patterns: List[str]) -> Optional[float]:
            for pat in patterns:
                for line in text.splitlines():
                    m = re.search(pat, line, re.IGNORECASE)
                    if m:
                        num = parse_numeric(m.group(1))
                        if num is not None:
                            return num
            return None

        tot_assets = find_money([r"\btotal\s*assets\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])
        tot_liab = find_money([r"\btotal\s*liabilities\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])
        tot_equity = find_money([r"\btotal\s*(?:shareholders'?|stockholders'?\s*)?equity\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])
        tot_cap_liab = find_money([r"\btotal\s*capital\s*(?:and|&)\s*liabilities\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])

        if tot_cap_liab is None and tot_liab is not None and tot_equity is not None:
            tot_cap_liab = round(tot_liab + tot_equity, 2)
        if tot_assets is None and tot_cap_liab is not None:
            tot_assets = tot_cap_liab

        data["total_assets"] = {"value": tot_assets, "confidence": 0.98 if tot_assets else 0.0, "page_number": 1}
        data["total_liabilities"] = {"value": tot_liab, "confidence": 0.97 if tot_liab else 0.0, "page_number": 1}
        data["total_equity"] = {"value": tot_equity, "confidence": 0.97 if tot_equity else 0.0, "page_number": 1}
        data["total_capital_and_liabilities"] = {"value": tot_cap_liab, "confidence": 0.98 if tot_cap_liab else 0.0, "page_number": 1}

        data["asset_components"] = []
        data["liability_equity_components"] = []

        curr_assets = find_money([r"\bcurrent\s*assets\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])
        non_curr_assets = find_money([r"\bnon-?current\s*assets\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])
        if curr_assets:
            data["asset_components"].append({"name": "Current Assets", "value": curr_assets})
        if non_curr_assets:
            data["asset_components"].append({"name": "Non-Current Assets", "value": non_curr_assets})

        curr_liab = find_money([r"\bcurrent\s*liabilities\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])
        non_curr_liab = find_money([r"\bnon-?current\s*liabilities\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])
        if curr_liab:
            data["liability_equity_components"].append({"name": "Current Liabilities", "value": curr_liab})
        if non_curr_liab:
            data["liability_equity_components"].append({"name": "Non-Current Liabilities", "value": non_curr_liab})
        if tot_equity:
            data["liability_equity_components"].append({"name": "Total Equity", "value": tot_equity})

        conf = cls._calculate_confidence(data)
        return data, conf

    @classmethod
    def _parse_pnl_heuristics(cls, text: str, page_records: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], float]:
        data: Dict[str, Any] = {}

        def find_money(patterns: List[str]) -> Optional[float]:
            for pat in patterns:
                for line in text.splitlines():
                    m = re.search(pat, line, re.IGNORECASE)
                    if m:
                        num = parse_numeric(m.group(1))
                        if num is not None:
                            return num
            return None

        interest_earned = find_money([r"\binterest\s*earned\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])
        other_income = find_money([r"\bother\s*income\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"]) or 0.0
        total_income = find_money([r"\btotal\s*income\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])

        interest_expended = find_money([r"\binterest\s*expended\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])
        opex = find_money([r"\boperating\s*expenses\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])
        provisions = find_money([r"\bprovisions\s*(?:and|&)\s*contingencies\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"]) or 0.0
        total_exp = find_money([r"\btotal\s*expenditure\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])

        revenue = find_money([r"\b(?:revenue|sales|turnover)\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])
        cogs = find_money([r"\b(?:cost\s*of\s*sales|cogs)\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])
        gross_profit = find_money([r"\bgross\s*profit\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])
        operating_profit = find_money([r"\boperating\s*profit\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])
        tax = find_money([r"\b(?:tax|taxation|income\s*tax)\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])
        net_profit = find_money([r"\bnet\s*profit\s*[:=]?\s*([$€£₹A-Z\s]*[\d,.]+)"])

        data["interest_earned"] = {"value": interest_earned, "confidence": 0.98 if interest_earned else 0.0, "page_number": 1}
        data["other_income"] = {"value": other_income, "confidence": 0.96, "page_number": 1}
        data["total_income"] = {"value": total_income or revenue, "confidence": 0.98 if (total_income or revenue) else 0.0, "page_number": 1}

        data["interest_expended"] = {"value": interest_expended, "confidence": 0.97 if interest_expended else 0.0, "page_number": 1}
        data["operating_expenses"] = {"value": opex, "confidence": 0.97 if opex else 0.0, "page_number": 1}
        data["provisions_and_contingencies"] = {"value": provisions, "confidence": 0.95, "page_number": 1}
        data["total_expenditure"] = {"value": total_exp or opex, "confidence": 0.98 if (total_exp or opex) else 0.0, "page_number": 1}

        data["revenue"] = {"value": revenue, "confidence": 0.98 if revenue else 0.0, "page_number": 1}
        data["cost_of_sales"] = {"value": cogs, "confidence": 0.97 if cogs else 0.0, "page_number": 1}
        data["gross_profit"] = {"value": gross_profit, "confidence": 0.98 if gross_profit else 0.0, "page_number": 1}
        data["operating_profit"] = {"value": operating_profit, "confidence": 0.98 if operating_profit else 0.0, "page_number": 1}
        data["tax"] = {"value": tax, "confidence": 0.97 if tax else 0.0, "page_number": 1}
        data["net_profit"] = {"value": net_profit, "confidence": 0.99 if net_profit else 0.0, "page_number": 1}

        conf = cls._calculate_confidence(data)
        return data, conf

    @classmethod
    def _parse_cash_flow_heuristics(cls, text: str, page_records: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], float]:
        data: Dict[str, Any] = {}

        def find_money(patterns: List[str]) -> Optional[float]:
            for pat in patterns:
                for line in text.splitlines():
                    m = re.search(pat, line, re.IGNORECASE)
                    if m:
                        num = parse_numeric(m.group(1))
                        if num is not None:
                            return num
            return None

        ocf = find_money([r"\b(?:operating\s*activities|operating\s*cash\s*flow)\s*[:=]?\s*([($€£₹A-Z\s]*[\d,.]+\)?)"])
        icf = find_money([r"\b(?:investing\s*activities|investing\s*cash\s*flow)\s*[:=]?\s*([($€£₹A-Z\s]*[\d,.]+\)?)"])
        fcf = find_money([r"\b(?:financing\s*activities|financing\s*cash\s*flow)\s*[:=]?\s*([($€£₹A-Z\s]*[\d,.]+\)?)"])
        fx = find_money([r"\b(?:fx|foreign\s*exchange|translation)\s*[:=]?\s*([($€£₹A-Z\s]*[\d,.]+\)?)"]) or 0.0
        net_inc = find_money([r"\b(?:net\s*increase|net\s*change)[\s\w]*[:=]?\s*([($€£₹A-Z\s]*[\d,.]+\)?)"])
        opening = find_money([r"\b(?:opening\s*cash|beginning\s*cash|cash\s*at\s*start)[\s\w]*[:=]?\s*([($€£₹A-Z\s]*[\d,.]+\)?)"])
        closing = find_money([r"\b(?:closing\s*cash|ending\s*cash|cash\s*at\s*end)[\s\w]*[:=]?\s*([($€£₹A-Z\s]*[\d,.]+\)?)"])

        data["operating_cash_flow"] = {"value": ocf, "confidence": 0.98 if ocf is not None else 0.0, "page_number": 1}
        data["investing_cash_flow"] = {"value": icf, "confidence": 0.97 if icf is not None else 0.0, "page_number": 1}
        data["financing_cash_flow"] = {"value": fcf, "confidence": 0.97 if fcf is not None else 0.0, "page_number": 1}
        data["fx_adjustment"] = {"value": fx, "confidence": 0.95, "page_number": 1}
        data["net_change_in_cash"] = {"value": net_inc, "confidence": 0.98 if net_inc is not None else 0.0, "page_number": 1}
        data["opening_cash"] = {"value": opening, "confidence": 0.98 if opening is not None else 0.0, "page_number": 1}
        data["closing_cash"] = {"value": closing, "confidence": 0.99 if closing is not None else 0.0, "page_number": 1}

        conf = cls._calculate_confidence(data)
        return data, conf

    @classmethod
    def _calculate_confidence(cls, data: Dict[str, Any]) -> float:
        """Computes explainable average confidence score from extracted fields."""
        scores: List[float] = []
        for k, v in data.items():
            if isinstance(v, dict) and "confidence" in v and v.get("value") is not None:
                scores.append(float(v["confidence"]))
        if not scores:
            return 0.85
        return round(sum(scores) / len(scores), 2)

    @classmethod
    def _get_extraction_prompt(cls, document_type: str) -> str:
        """Returns targeted structured prompt for LLM models."""
        return f"""
You are an expert Document Intelligence Extraction system.
Analyze the provided document and extract ALL available fields, financial line items, and tables for a '{document_type}'.

CRITICAL INSTRUCTIONS:
1. Extract ALL visible information accurately as strict JSON.
2. For each key field, return an object: {{"value": <value_or_null>, "confidence": <0.0_to_1.0>, "page_number": <page_num>, "evidence": {{"source_text": "<exact_snippet>", "page_number": <page_num>}}}}
3. Missing fields MUST be returned with "value": null. Do NOT invent or infer values.
4. Cleanly parse numbers as floats. Parentheses or brackets like (1,250.00) represent negative numbers (-1250.00).
5. Extract tables/line-items as structured arrays.

Output JSON structure must strictly follow the document type '{document_type}'.
"""
