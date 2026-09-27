"""Financial validation engine executing required accounting and arithmetic checks."""

from typing import Any, Dict, List, Optional
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.schemas.extraction import ValidationCheck, ValidationSummary
from backend.app.utils.helpers import parse_numeric, compare_with_tolerance


class FinancialValidationService:
    """Performs financial reconciliation and arithmetic integrity checks."""

    @classmethod
    def validate(cls, document_type: str, extracted_data: Dict[str, Any]) -> ValidationSummary:
        """
        Executes financial checks based on document type.
        Returns a ValidationSummary containing all checks, overall status, and issue logs.
        """
        logger.info(f"Running financial validations for document type: '{document_type}'")
        checks: List[ValidationCheck] = []
        issues: List[str] = []

        if not extracted_data:
            return ValidationSummary(
                checks=[],
                overall_status="FAIL",
                issues=["Extracted data is empty; validations could not be performed."]
            )

        doc_type_clean = document_type.lower().strip()

        if doc_type_clean == "invoice":
            cls._validate_invoice(extracted_data, checks, issues)
        elif doc_type_clean == "balance_sheet":
            cls._validate_balance_sheet(extracted_data, checks, issues)
        elif doc_type_clean == "profit_and_loss":
            cls._validate_profit_and_loss(extracted_data, checks, issues)
        elif doc_type_clean == "cash_flow_statement":
            cls._validate_cash_flow_statement(extracted_data, checks, issues)
        else:
            issues.append(f"Unrecognized document type '{document_type}' for financial validation.")

        # Determine overall status: FAIL if any check explicitly failed
        has_failure = any(check.status == "FAIL" for check in checks)
        overall_status = "FAIL" if has_failure or (not checks and issues) else "PASS"

        logger.info(
            f"Financial validation completed: {overall_status} ({len(checks)} checks evaluated, {len(issues)} issues)"
        )
        return ValidationSummary(
            checks=checks,
            overall_status=overall_status,
            issues=issues
        )

    @classmethod
    def _extract_val(cls, extracted_data: Dict[str, Any], key: str) -> Optional[float]:
        """Extracts and parses a numeric value from extracted_data (supports nested {'value': ...})."""
        raw = extracted_data.get(key)
        if isinstance(raw, dict) and "value" in raw:
            raw = raw["value"]
        return parse_numeric(raw)

    # --------------------------------------------------------------------------
    # 1. INVOICE VALIDATION
    # --------------------------------------------------------------------------
    @classmethod
    def _validate_invoice(cls, data: Dict[str, Any], checks: List[ValidationCheck], issues: List[str]) -> None:
        subtotal = cls._extract_val(data, "subtotal")
        tax_amount = cls._extract_val(data, "tax_amount")
        discount = cls._extract_val(data, "discount") or 0.0
        total_amount = cls._extract_val(data, "total_amount")
        cash_paid = cls._extract_val(data, "cash_paid")
        change = cls._extract_val(data, "change")
        line_items = data.get("line_items", [])

        # Check 1: Line Items Quantity * Unit Price ≈ Line Total
        if isinstance(line_items, list) and line_items:
            for idx, item in enumerate(line_items):
                if isinstance(item, dict):
                    qty = parse_numeric(item.get("quantity"))
                    u_price = parse_numeric(item.get("unit_price"))
                    line_amt = parse_numeric(item.get("amount"))

                    if qty is not None and u_price is not None:
                        calc_line = round(qty * u_price, 2)
                        if line_amt is not None:
                            ok, var = compare_with_tolerance(calc_line, line_amt, settings.FINANCIAL_TOLERANCE)
                            status = "PASS" if ok else "FAIL"
                            if not ok:
                                issues.append(
                                    f"Line item {idx+1} calculation failed: {qty} * {u_price} = {calc_line} != {line_amt} (var: {var})"
                                )
                        else:
                            status = "NOT_APPLICABLE"
                            var = None
                            line_amt = None

                        checks.append(ValidationCheck(
                            name=f"line_item_{idx+1}_total_check",
                            formula="quantity * unit_price",
                            operands={"quantity": qty, "unit_price": u_price},
                            calculated_value=calc_line,
                            reported_value=line_amt,
                            variance=var,
                            status=status
                        ))

            # Check 2: Sum of all line totals ≈ Subtotal or Total
            valid_amounts = [parse_numeric(item.get("amount")) for item in line_items if isinstance(item, dict)]
            if all(v is not None for v in valid_amounts) and valid_amounts:
                calc_sum = round(sum(valid_amounts), 2)
                target_reported = subtotal if subtotal is not None else total_amount
                target_name = "subtotal" if subtotal is not None else "total_amount"

                if target_reported is not None:
                    ok, var = compare_with_tolerance(calc_sum, target_reported, settings.FINANCIAL_TOLERANCE)
                    status = "PASS" if ok else "FAIL"
                    if not ok:
                        issues.append(
                            f"Sum of line items ({calc_sum}) does not reconcile with reported {target_name} ({target_reported})."
                        )
                else:
                    status = "NOT_APPLICABLE"
                    var = None

                checks.append(ValidationCheck(
                    name="line_items_sum_reconciliation",
                    formula="sum(line_items.amount)",
                    operands={"line_totals_sum": calc_sum},
                    calculated_value=calc_sum,
                    reported_value=target_reported,
                    variance=var,
                    status=status
                ))

        # Check 3: Invoice Total Check (Subtotal + Tax - Discount ≈ Total)
        if subtotal is not None and total_amount is not None:
            # Handle GST/Tax Inclusive case:
            # If subtotal equals total_amount and tax_amount > 0, tax may already be included in total
            tax_val = tax_amount if tax_amount is not None else 0.0
            calc_total_standard = round(subtotal + tax_val - discount, 2)
            ok_std, var_std = compare_with_tolerance(calc_total_standard, total_amount, settings.FINANCIAL_TOLERANCE)

            # Check if tax is already included: subtotal - discount ≈ total
            calc_tax_inclusive = round(subtotal - discount, 2)
            ok_inc, var_inc = compare_with_tolerance(calc_tax_inclusive, total_amount, settings.FINANCIAL_TOLERANCE)

            if ok_std:
                checks.append(ValidationCheck(
                    name="invoice_total_check",
                    formula="subtotal + tax_amount - discount",
                    operands={"subtotal": subtotal, "tax_amount": tax_val, "discount": discount},
                    calculated_value=calc_total_standard,
                    reported_value=total_amount,
                    variance=var_std,
                    status="PASS"
                ))
            elif ok_inc:
                checks.append(ValidationCheck(
                    name="invoice_total_check",
                    formula="subtotal - discount (tax inclusive)",
                    operands={"subtotal": subtotal, "tax_amount": tax_val, "discount": discount, "tax_inclusive": True},
                    calculated_value=calc_tax_inclusive,
                    reported_value=total_amount,
                    variance=var_inc,
                    status="PASS"
                ))
            else:
                issues.append(
                    f"Invoice total check failed: {subtotal} + {tax_val} - {discount} = {calc_total_standard} != reported {total_amount} (variance: {var_std})"
                )
                checks.append(ValidationCheck(
                    name="invoice_total_check",
                    formula="subtotal + tax_amount - discount",
                    operands={"subtotal": subtotal, "tax_amount": tax_val, "discount": discount},
                    calculated_value=calc_total_standard,
                    reported_value=total_amount,
                    variance=var_std,
                    status="FAIL"
                ))
        else:
            checks.append(ValidationCheck(
                name="invoice_total_check",
                formula="subtotal + tax_amount - discount",
                operands={"subtotal": subtotal, "tax_amount": tax_amount, "discount": discount},
                calculated_value=None,
                reported_value=total_amount,
                variance=None,
                status="NOT_APPLICABLE"
            ))

        # Check 4: Cash Paid - Total Amount ≈ Change
        if cash_paid is not None and total_amount is not None:
            calc_change = round(cash_paid - total_amount, 2)
            if change is not None:
                ok, var = compare_with_tolerance(calc_change, change, settings.FINANCIAL_TOLERANCE)
                status = "PASS" if ok else "FAIL"
                if not ok:
                    issues.append(
                        f"Cash change check failed: {cash_paid} - {total_amount} = {calc_change} != reported change {change}"
                    )
            else:
                status = "NOT_APPLICABLE"
                var = None

            checks.append(ValidationCheck(
                name="cash_change_check",
                formula="cash_paid - total_amount",
                operands={"cash_paid": cash_paid, "total_amount": total_amount},
                calculated_value=calc_change,
                reported_value=change,
                variance=var,
                status=status
            ))

    # --------------------------------------------------------------------------
    # 2. BALANCE SHEET VALIDATION
    # --------------------------------------------------------------------------
    @classmethod
    def _validate_balance_sheet(cls, data: Dict[str, Any], checks: List[ValidationCheck], issues: List[str]) -> None:
        # Check if comparative periods exist (e.g. data['periods'] = {'2024': {...}, '2023': {...}})
        periods_dict = data.get("periods")
        if isinstance(periods_dict, dict) and periods_dict:
            for p_name, p_data in periods_dict.items():
                if isinstance(p_data, dict):
                    cls._validate_balance_sheet_period(p_data, checks, issues, prefix=f"period_{p_name}")
        else:
            cls._validate_balance_sheet_period(data, checks, issues, prefix="current")

    @classmethod
    def _validate_balance_sheet_period(
        cls,
        period_data: Dict[str, Any],
        checks: List[ValidationCheck],
        issues: List[str],
        prefix: str
    ) -> None:
        total_assets = cls._extract_val(period_data, "total_assets")
        total_liabilities = cls._extract_val(period_data, "total_liabilities")
        total_equity = cls._extract_val(period_data, "total_equity")
        total_capital_liabilities = cls._extract_val(period_data, "total_capital_and_liabilities")
        
        # Check 1: Total Capital & Liabilities ≈ Total Assets
        if total_capital_liabilities is not None and total_assets is not None:
            ok, var = compare_with_tolerance(total_capital_liabilities, total_assets, settings.FINANCIAL_TOLERANCE)
            status = "PASS" if ok else "FAIL"
            if not ok:
                issues.append(
                    f"[{prefix}] Balance sheet equation failed: Capital & Liabilities ({total_capital_liabilities}) != Assets ({total_assets}) (var: {var})"
                )
            checks.append(ValidationCheck(
                name=f"{prefix}_balance_sheet_equation",
                formula="total_capital_and_liabilities ≈ total_assets",
                operands={"total_capital_and_liabilities": total_capital_liabilities, "total_assets": total_assets},
                calculated_value=total_capital_liabilities,
                reported_value=total_assets,
                variance=var,
                status=status
            ))
        elif total_liabilities is not None and total_equity is not None and total_assets is not None:
            calc_cap_liab = round(total_liabilities + total_equity, 2)
            ok, var = compare_with_tolerance(calc_cap_liab, total_assets, settings.FINANCIAL_TOLERANCE)
            status = "PASS" if ok else "FAIL"
            if not ok:
                issues.append(
                    f"[{prefix}] Liabilities + Equity ({calc_cap_liab}) != Assets ({total_assets}) (var: {var})"
                )
            checks.append(ValidationCheck(
                name=f"{prefix}_balance_sheet_equation",
                formula="total_liabilities + total_equity ≈ total_assets",
                operands={"total_liabilities": total_liabilities, "total_equity": total_equity},
                calculated_value=calc_cap_liab,
                reported_value=total_assets,
                variance=var,
                status=status
            ))
        else:
            checks.append(ValidationCheck(
                name=f"{prefix}_balance_sheet_equation",
                formula="total_capital_and_liabilities ≈ total_assets",
                operands={"total_assets": total_assets, "total_liabilities": total_liabilities, "total_equity": total_equity},
                calculated_value=None,
                reported_value=total_assets,
                variance=None,
                status="NOT_APPLICABLE"
            ))

        # Check 2: Sum of individual Asset components reconciles to Total Assets
        asset_items = period_data.get("asset_components") or period_data.get("assets", [])
        if isinstance(asset_items, list) and asset_items:
            valid_vals = [parse_numeric(item.get("value") if isinstance(item, dict) else item) for item in asset_items]
            if all(v is not None for v in valid_vals) and valid_vals and total_assets is not None:
                calc_asset_sum = round(sum(valid_vals), 2)
                ok, var = compare_with_tolerance(calc_asset_sum, total_assets, settings.FINANCIAL_TOLERANCE)
                status = "PASS" if ok else "FAIL"
                if not ok:
                    issues.append(
                        f"[{prefix}] Asset components sum ({calc_asset_sum}) does not match Total Assets ({total_assets})."
                    )
                checks.append(ValidationCheck(
                    name=f"{prefix}_asset_components_sum",
                    formula="sum(asset_components)",
                    operands={"components_sum": calc_asset_sum},
                    calculated_value=calc_asset_sum,
                    reported_value=total_assets,
                    variance=var,
                    status=status
                ))

        # Check 3: Sum of Capital & Liability components reconciles to Total Capital & Liabilities
        cap_items = period_data.get("liability_equity_components") or period_data.get("liabilities_and_equity", [])
        target_cap = total_capital_liabilities or (total_liabilities + total_equity if (total_liabilities and total_equity) else None)
        if isinstance(cap_items, list) and cap_items and target_cap is not None:
            valid_vals = [parse_numeric(item.get("value") if isinstance(item, dict) else item) for item in cap_items]
            if all(v is not None for v in valid_vals) and valid_vals:
                calc_cap_sum = round(sum(valid_vals), 2)
                ok, var = compare_with_tolerance(calc_cap_sum, target_cap, settings.FINANCIAL_TOLERANCE)
                status = "PASS" if ok else "FAIL"
                if not ok:
                    issues.append(
                        f"[{prefix}] Capital & Liabilities sum ({calc_cap_sum}) does not match total ({target_cap})."
                    )
                checks.append(ValidationCheck(
                    name=f"{prefix}_capital_liabilities_components_sum",
                    formula="sum(capital_and_liability_components)",
                    operands={"components_sum": calc_cap_sum},
                    calculated_value=calc_cap_sum,
                    reported_value=target_cap,
                    variance=var,
                    status=status
                ))

    # --------------------------------------------------------------------------
    # 3. PROFIT & LOSS VALIDATION
    # --------------------------------------------------------------------------
    @classmethod
    def _validate_profit_and_loss(cls, data: Dict[str, Any], checks: List[ValidationCheck], issues: List[str]) -> None:
        periods_dict = data.get("periods")
        if isinstance(periods_dict, dict) and periods_dict:
            for p_name, p_data in periods_dict.items():
                if isinstance(p_data, dict):
                    cls._validate_pnl_period(p_data, checks, issues, prefix=f"period_{p_name}")
        else:
            cls._validate_pnl_period(data, checks, issues, prefix="current")

    @classmethod
    def _validate_pnl_period(
        cls,
        p_data: Dict[str, Any],
        checks: List[ValidationCheck],
        issues: List[str],
        prefix: str
    ) -> None:
        interest_earned = cls._extract_val(p_data, "interest_earned")
        other_income = cls._extract_val(p_data, "other_income")
        total_income = cls._extract_val(p_data, "total_income")

        interest_expended = cls._extract_val(p_data, "interest_expended")
        operating_expenses = cls._extract_val(p_data, "operating_expenses")
        provisions = cls._extract_val(p_data, "provisions_and_contingencies")
        total_expenditure = cls._extract_val(p_data, "total_expenditure")

        profit_before_minority = cls._extract_val(p_data, "profit_before_minority_interest") or cls._extract_val(p_data, "consolidated_net_profit_before_minority_interest")
        minority_interest = cls._extract_val(p_data, "minority_interest")
        net_profit_group = cls._extract_val(p_data, "consolidated_net_profit") or cls._extract_val(p_data, "net_profit")

        current_profit = cls._extract_val(p_data, "current_profit")
        brought_forward_profit = cls._extract_val(p_data, "brought_forward_profit")
        total_available_for_appropriation = cls._extract_val(p_data, "total_available_for_appropriation")

        # Standard Corporate Format Fallbacks:
        revenue = cls._extract_val(p_data, "revenue")
        cost_of_sales = cls._extract_val(p_data, "cost_of_sales") or cls._extract_val(p_data, "cogs")
        gross_profit = cls._extract_val(p_data, "gross_profit")
        operating_profit = cls._extract_val(p_data, "operating_profit")
        tax = cls._extract_val(p_data, "tax")

        # Check 1: Interest Earned + Other Income ≈ Total Income (or Revenue + Other Income ≈ Total Income)
        inc_component_1 = interest_earned if interest_earned is not None else revenue
        if inc_component_1 is not None and other_income is not None and total_income is not None:
            calc_income = round(inc_component_1 + other_income, 2)
            ok, var = compare_with_tolerance(calc_income, total_income, settings.FINANCIAL_TOLERANCE)
            status = "PASS" if ok else "FAIL"
            if not ok:
                issues.append(f"[{prefix}] Total income check failed: {inc_component_1} + {other_income} = {calc_income} != {total_income}")
            checks.append(ValidationCheck(
                name=f"{prefix}_total_income_check",
                formula="interest_earned (or revenue) + other_income",
                operands={"primary_income": inc_component_1, "other_income": other_income},
                calculated_value=calc_income,
                reported_value=total_income,
                variance=var,
                status=status
            ))
        else:
            checks.append(ValidationCheck(
                name=f"{prefix}_total_income_check",
                formula="interest_earned + other_income ≈ total_income",
                operands={"interest_earned": interest_earned, "other_income": other_income},
                calculated_value=None,
                reported_value=total_income,
                variance=None,
                status="NOT_APPLICABLE"
            ))

        # Check 2: Interest Expended + Operating Expenses + Provisions ≈ Total Expenditure
        if interest_expended is not None and operating_expenses is not None and total_expenditure is not None:
            prov_val = provisions if provisions is not None else 0.0
            calc_exp = round(interest_expended + operating_expenses + prov_val, 2)
            ok, var = compare_with_tolerance(calc_exp, total_expenditure, settings.FINANCIAL_TOLERANCE)
            status = "PASS" if ok else "FAIL"
            if not ok:
                issues.append(f"[{prefix}] Total expenditure check failed: calc {calc_exp} != {total_expenditure}")
            checks.append(ValidationCheck(
                name=f"{prefix}_total_expenditure_check",
                formula="interest_expended + operating_expenses + provisions",
                operands={"interest_expended": interest_expended, "operating_expenses": operating_expenses, "provisions": prov_val},
                calculated_value=calc_exp,
                reported_value=total_expenditure,
                variance=var,
                status=status
            ))
        elif cost_of_sales is not None and operating_expenses is not None and total_expenditure is not None:
            calc_exp = round(cost_of_sales + operating_expenses, 2)
            ok, var = compare_with_tolerance(calc_exp, total_expenditure, settings.FINANCIAL_TOLERANCE)
            status = "PASS" if ok else "FAIL"
            checks.append(ValidationCheck(
                name=f"{prefix}_total_expenditure_check",
                formula="cost_of_sales + operating_expenses",
                operands={"cost_of_sales": cost_of_sales, "operating_expenses": operating_expenses},
                calculated_value=calc_exp,
                reported_value=total_expenditure,
                variance=var,
                status=status
            ))
        else:
            checks.append(ValidationCheck(
                name=f"{prefix}_total_expenditure_check",
                formula="interest_expended + operating_expenses + provisions ≈ total_expenditure",
                operands={"interest_expended": interest_expended, "operating_expenses": operating_expenses},
                calculated_value=None,
                reported_value=total_expenditure,
                variance=None,
                status="NOT_APPLICABLE"
            ))

        # Check 3: Total Income - Total Expenditure ≈ Profit before Minority Interest
        if total_income is not None and total_expenditure is not None:
            calc_profit_before_min = round(total_income - total_expenditure, 2)
            target_rep = profit_before_minority if profit_before_minority is not None else net_profit_group
            if target_rep is not None:
                ok, var = compare_with_tolerance(calc_profit_before_min, target_rep, settings.FINANCIAL_TOLERANCE)
                status = "PASS" if ok else "FAIL"
                if not ok:
                    issues.append(f"[{prefix}] Net profit before minority check failed: {calc_profit_before_min} != {target_rep}")
                checks.append(ValidationCheck(
                    name=f"{prefix}_profit_before_minority_interest_check",
                    formula="total_income - total_expenditure",
                    operands={"total_income": total_income, "total_expenditure": total_expenditure},
                    calculated_value=calc_profit_before_min,
                    reported_value=target_rep,
                    variance=var,
                    status=status
                ))
            else:
                checks.append(ValidationCheck(
                    name=f"{prefix}_profit_before_minority_interest_check",
                    formula="total_income - total_expenditure",
                    operands={"total_income": total_income, "total_expenditure": total_expenditure},
                    calculated_value=calc_profit_before_min,
                    reported_value=None,
                    variance=None,
                    status="NOT_APPLICABLE"
                ))
        else:
            checks.append(ValidationCheck(
                name=f"{prefix}_profit_before_minority_interest_check",
                formula="total_income - total_expenditure",
                operands={"total_income": total_income, "total_expenditure": total_expenditure},
                calculated_value=None,
                reported_value=profit_before_minority,
                variance=None,
                status="NOT_APPLICABLE"
            ))

        # Check 4: Profit before Minority Interest - Minority Interest ≈ Consolidated Net Profit
        if profit_before_minority is not None and minority_interest is not None and net_profit_group is not None:
            calc_net_profit = round(profit_before_minority - minority_interest, 2)
            ok, var = compare_with_tolerance(calc_net_profit, net_profit_group, settings.FINANCIAL_TOLERANCE)
            status = "PASS" if ok else "FAIL"
            if not ok:
                issues.append(f"[{prefix}] Consolidated net profit attributable check failed: {calc_net_profit} != {net_profit_group}")
            checks.append(ValidationCheck(
                name=f"{prefix}_consolidated_net_profit_attributable_check",
                formula="profit_before_minority_interest - minority_interest",
                operands={"profit_before_minority_interest": profit_before_minority, "minority_interest": minority_interest},
                calculated_value=calc_net_profit,
                reported_value=net_profit_group,
                variance=var,
                status=status
            ))
        else:
            checks.append(ValidationCheck(
                name=f"{prefix}_consolidated_net_profit_attributable_check",
                formula="profit_before_minority_interest - minority_interest",
                operands={"profit_before_minority": profit_before_minority, "minority_interest": minority_interest},
                calculated_value=None,
                reported_value=net_profit_group,
                variance=None,
                status="NOT_APPLICABLE"
            ))

        # Check 5: Current Profit + Brought Forward Profit ≈ Total Available for Appropriation
        if current_profit is not None and brought_forward_profit is not None and total_available_for_appropriation is not None:
            calc_approp = round(current_profit + brought_forward_profit, 2)
            ok, var = compare_with_tolerance(calc_approp, total_available_for_appropriation, settings.FINANCIAL_TOLERANCE)
            status = "PASS" if ok else "FAIL"
            if not ok:
                issues.append(f"[{prefix}] Appropriation check failed: {calc_approp} != {total_available_for_appropriation}")
            checks.append(ValidationCheck(
                name=f"{prefix}_appropriation_check",
                formula="current_profit + brought_forward_profit",
                operands={"current_profit": current_profit, "brought_forward_profit": brought_forward_profit},
                calculated_value=calc_approp,
                reported_value=total_available_for_appropriation,
                variance=var,
                status=status
            ))

        # Check 6: Corporate Format Gross Profit & Operating Profit checks (if applicable)
        if revenue is not None and cost_of_sales is not None and gross_profit is not None:
            calc_gp = round(revenue - cost_of_sales, 2)
            ok, var = compare_with_tolerance(calc_gp, gross_profit, settings.FINANCIAL_TOLERANCE)
            status = "PASS" if ok else "FAIL"
            checks.append(ValidationCheck(
                name=f"{prefix}_gross_profit_check",
                formula="revenue - cost_of_sales",
                operands={"revenue": revenue, "cost_of_sales": cost_of_sales},
                calculated_value=calc_gp,
                reported_value=gross_profit,
                variance=var,
                status=status
            ))

        if gross_profit is not None and operating_expenses is not None and operating_profit is not None:
            calc_op = round(gross_profit - operating_expenses, 2)
            ok, var = compare_with_tolerance(calc_op, operating_profit, settings.FINANCIAL_TOLERANCE)
            status = "PASS" if ok else "FAIL"
            checks.append(ValidationCheck(
                name=f"{prefix}_operating_profit_check",
                formula="gross_profit - operating_expenses",
                operands={"gross_profit": gross_profit, "operating_expenses": operating_expenses},
                calculated_value=calc_op,
                reported_value=operating_profit,
                variance=var,
                status=status
            ))

        if operating_profit is not None and tax is not None and net_profit_group is not None:
            calc_np = round(operating_profit - tax, 2)
            ok, var = compare_with_tolerance(calc_np, net_profit_group, settings.FINANCIAL_TOLERANCE)
            status = "PASS" if ok else "FAIL"
            checks.append(ValidationCheck(
                name=f"{prefix}_net_profit_after_tax_check",
                formula="operating_profit - tax",
                operands={"operating_profit": operating_profit, "tax": tax},
                calculated_value=calc_np,
                reported_value=net_profit_group,
                variance=var,
                status=status
            ))

    # --------------------------------------------------------------------------
    # 4. CASH FLOW STATEMENT VALIDATION
    # --------------------------------------------------------------------------
    @classmethod
    def _validate_cash_flow_statement(cls, data: Dict[str, Any], checks: List[ValidationCheck], issues: List[str]) -> None:
        periods_dict = data.get("periods")
        if isinstance(periods_dict, dict) and periods_dict:
            for p_name, p_data in periods_dict.items():
                if isinstance(p_data, dict):
                    cls._validate_cash_flow_period(p_data, checks, issues, prefix=f"period_{p_name}")
        else:
            cls._validate_cash_flow_period(data, checks, issues, prefix="current")

    @classmethod
    def _validate_cash_flow_period(
        cls,
        p_data: Dict[str, Any],
        checks: List[ValidationCheck],
        issues: List[str],
        prefix: str
    ) -> None:
        ocf = cls._extract_val(p_data, "operating_cash_flow") or cls._extract_val(p_data, "cash_flow_from_operating_activities")
        icf = cls._extract_val(p_data, "investing_cash_flow") or cls._extract_val(p_data, "cash_flow_from_investing_activities")
        fcf = cls._extract_val(p_data, "financing_cash_flow") or cls._extract_val(p_data, "cash_flow_from_financing_activities")
        fx_adj = cls._extract_val(p_data, "fx_adjustment") or cls._extract_val(p_data, "translation_adjustment") or 0.0
        net_increase = cls._extract_val(p_data, "net_change_in_cash") or cls._extract_val(p_data, "net_increase_in_cash") or cls._extract_val(p_data, "net_increase_in_cash_and_cash_equivalents")

        opening_cash = cls._extract_val(p_data, "opening_cash") or cls._extract_val(p_data, "opening_cash_and_cash_equivalents")
        closing_cash = cls._extract_val(p_data, "closing_cash") or cls._extract_val(p_data, "closing_cash_and_cash_equivalents")
        adjustments = cls._extract_val(p_data, "cash_acquired_on_amalgamation") or cls._extract_val(p_data, "other_applicable_adjustments") or 0.0

        # Check 1: OCF + ICF + FCF + FX ≈ Net Increase in Cash & Cash Equivalents
        if ocf is not None and icf is not None and fcf is not None and net_increase is not None:
            calc_net = round(ocf + icf + fcf + fx_adj, 2)
            ok, var = compare_with_tolerance(calc_net, net_increase, settings.FINANCIAL_TOLERANCE)
            status = "PASS" if ok else "FAIL"
            if not ok:
                issues.append(
                    f"[{prefix}] Cash flow net change check failed: {ocf} + {icf} + {fcf} + {fx_adj} = {calc_net} != reported {net_increase} (variance: {var})"
                )
            checks.append(ValidationCheck(
                name=f"{prefix}_net_cash_flow_check",
                formula="operating_cash_flow + investing_cash_flow + financing_cash_flow + fx_adjustment",
                operands={"operating_cash_flow": ocf, "investing_cash_flow": icf, "financing_cash_flow": fcf, "fx_adjustment": fx_adj},
                calculated_value=calc_net,
                reported_value=net_increase,
                variance=var,
                status=status
            ))
        else:
            checks.append(ValidationCheck(
                name=f"{prefix}_net_cash_flow_check",
                formula="operating_cash_flow + investing_cash_flow + financing_cash_flow + fx_adjustment",
                operands={"operating_cash_flow": ocf, "investing_cash_flow": icf, "financing_cash_flow": fcf},
                calculated_value=None,
                reported_value=net_increase,
                variance=None,
                status="NOT_APPLICABLE"
            ))

        # Check 2: Opening Cash + Net Increase + Adjustments ≈ Closing Cash & Cash Equivalents
        if opening_cash is not None and net_increase is not None and closing_cash is not None:
            calc_closing = round(opening_cash + net_increase + adjustments, 2)
            ok, var = compare_with_tolerance(calc_closing, closing_cash, settings.FINANCIAL_TOLERANCE)
            status = "PASS" if ok else "FAIL"
            if not ok:
                issues.append(
                    f"[{prefix}] Closing cash reconciliation failed: {opening_cash} + {net_increase} + {adjustments} = {calc_closing} != reported {closing_cash} (variance: {var})"
                )
            checks.append(ValidationCheck(
                name=f"{prefix}_closing_cash_reconciliation_check",
                formula="opening_cash + net_increase_in_cash + adjustments",
                operands={"opening_cash": opening_cash, "net_increase": net_increase, "adjustments": adjustments},
                calculated_value=calc_closing,
                reported_value=closing_cash,
                variance=var,
                status=status
            ))
        else:
            checks.append(ValidationCheck(
                name=f"{prefix}_closing_cash_reconciliation_check",
                formula="opening_cash + net_increase_in_cash + adjustments",
                operands={"opening_cash": opening_cash, "net_increase": net_increase},
                calculated_value=None,
                reported_value=closing_cash,
                variance=None,
                status="NOT_APPLICABLE"
            ))
