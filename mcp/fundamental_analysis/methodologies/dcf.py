from typing import Dict, List
from core.schemas import ValuationRequest, ValuationResult
from methodologies.base import BaseMethodology

class DCFMethodology(BaseMethodology):
    """
    Discounted Cash Flow (DCF) valuation methodology.
    """

    @property
    def name(self) -> str:
        return "DCF"

    def calculate(
        self,
        request: ValuationRequest,
        financial_data: Dict[str, float],
        peers: List[Dict[str, float]]
    ) -> ValuationResult:
        
        fallback_applied = False
        assumptions = []
        
        # 1. Extract inputs
        current_price = financial_data.get("current_price", 0.0)
        shares_outstanding = financial_data.get("shares_outstanding", 0.0)
        market_cap = financial_data.get("market_cap", 0.0) or (current_price * shares_outstanding)
        total_debt = financial_data.get("total_debt", 0.0)
        total_cash = financial_data.get("total_cash", 0.0)
        revenue = financial_data.get("total_revenue", 0.0)
        ocf = financial_data.get("operating_cash_flow", 0.0)
        fcf = financial_data.get("free_cash_flow", 0.0)
        
        # Check critical input requirements for DCF:
        if shares_outstanding <= 0:
            return self.create_diagnostic_result(
                reason_code="MISSING_DATA",
                explanation="Shares outstanding must be positive to compute intrinsic value per share.",
                triggering_metrics={"shares_outstanding": shares_outstanding},
                analytical_implication="The company's shares outstanding data is not available, which prevents converting the aggregate equity value into a per-share value.",
                baseline_metrics={
                    "shares_outstanding": shares_outstanding,
                    "current_price": current_price
                }
            )
        
        # 2. Free Cash Flow (FCF) base resolution using historical cash flow hierarchy
        import statistics
        
        # Extract cashflow history arrays
        fcf_history = financial_data.get("free_cash_flow_history", [])
        ocf_history = financial_data.get("operating_cash_flow_history", [])
        capex_history = financial_data.get("capex_history", [])

        # Limit to the most recent 4 years
        fcf_history = fcf_history[:4]
        ocf_history = ocf_history[:4]
        capex_history = capex_history[:4]

        # Provide fallbacks if histories are empty but single values are present
        if not fcf_history and financial_data.get("free_cash_flow") is not None:
            fcf_history = [financial_data["free_cash_flow"]]
        if not ocf_history and financial_data.get("operating_cash_flow") is not None:
            ocf_history = [financial_data["operating_cash_flow"]]
        if not capex_history:
            if len(ocf_history) == len(fcf_history):
                capex_history = [abs(o - f) for o, f in zip(ocf_history, fcf_history)]
            else:
                fcf_val = financial_data.get("free_cash_flow", 0.0)
                ocf_val = financial_data.get("operating_cash_flow", 0.0)
                capex_history = [abs(ocf_val - fcf_val)]

        total_fcf_years = len(fcf_history)
        negative_fcf_count = sum(1 for val in fcf_history if val <= 0.0)

        base_fcf = 0.0
        
        use_normalized = False
        if request.adjustment_params and "use_normalized_fcf" in request.adjustment_params:
            use_normalized = request.adjustment_params["use_normalized_fcf"]
        else:
            use_normalized = (total_fcf_years > 0 and (negative_fcf_count / total_fcf_years) >= 0.5)

        if use_normalized:
            # Switch path: FCF is negative in >= 50% of available years
            total_ocf_years = len(ocf_history)
            negative_ocf_count = sum(1 for val in ocf_history if val <= 0.0)
            
            if total_ocf_years > 0 and (negative_ocf_count / total_ocf_years) >= 0.5:
                # OCF is consistently negative, abort as unreliable
                return self.create_diagnostic_result(
                    reason_code="INSUFFICIENT_CASH_GENERATION",
                    explanation="Insufficient cash-generation quality for a reliable DCF.",
                    triggering_metrics={
                        "free_cash_flow_history": fcf_history,
                        "operating_cash_flow_history": ocf_history
                    },
                    analytical_implication="The company does not generate positive cash from its operations, making it unsuitable for a growth-based discounted cash flow valuation.",
                    baseline_metrics={
                        "free_cash_flow": financial_data.get("free_cash_flow", 0.0),
                        "operating_cash_flow": financial_data.get("operating_cash_flow", 0.0),
                        "shares_outstanding": shares_outstanding,
                        "current_price": current_price
                    }
                )
            
            # Switch to normalized OCF minus estimated maintenance Capex (0.5 * median of Capex)
            median_ocf = statistics.median(ocf_history) if ocf_history else 0.0
            
            if capex_history:
                estimated_capex = 0.5 * statistics.median(capex_history)
            else:
                estimated_capex = 0.05 * financial_data.get("total_revenue", 0.0)
                
            base_fcf = median_ocf - estimated_capex
            fallback_applied = True
            
            if base_fcf <= 0.0:
                # Resulting FCF base is still <= 0, abort as unreliable
                return self.create_diagnostic_result(
                    reason_code="INSUFFICIENT_CASH_GENERATION",
                    explanation="Insufficient cash-generation quality for a reliable DCF.",
                    triggering_metrics={
                        "free_cash_flow_history": fcf_history,
                        "operating_cash_flow_history": ocf_history,
                        "capex_history": capex_history,
                        "adjusted_fcf_base": base_fcf
                    },
                    analytical_implication="The company's adjusted cash flow base after maintenance capex subtraction is negative or zero, making it unsuitable for DCF valuation.",
                    baseline_metrics={
                        "free_cash_flow": financial_data.get("free_cash_flow", 0.0),
                        "operating_cash_flow": financial_data.get("operating_cash_flow", 0.0),
                        "shares_outstanding": shares_outstanding,
                        "current_price": current_price
                    }
                )
            
            assumptions.append(f"Using normalized FCF base ({base_fcf:,.2f}) derived from Operating Cash Flow and maintenance Capex fallback")
        else:
            # Primary path: FCF is positive in the majority of years
            median_fcf = statistics.median(fcf_history) if fcf_history else 0.0
            if median_fcf <= 0.0:
                return self.create_diagnostic_result(
                    reason_code="INSUFFICIENT_CASH_GENERATION",
                    explanation="Insufficient cash-generation quality for a reliable DCF.",
                    triggering_metrics={
                        "free_cash_flow_history": fcf_history
                    },
                    analytical_implication="The median of historical free cash flows is negative or zero, preventing a reliable DCF forecast.",
                    baseline_metrics={
                        "free_cash_flow": financial_data.get("free_cash_flow", 0.0),
                        "shares_outstanding": shares_outstanding,
                        "current_price": current_price
                    }
                )
            base_fcf = median_fcf
            assumptions.append(f"Using reported Free Cash Flow of {base_fcf:,.2f} as base")


        # 3. Resolve growth rate
        rev_growth = financial_data.get("revenue_growth", 0.05)
        growth_rate = 0.05  # Default 5%
        if 0.01 <= rev_growth <= 0.25:
            growth_rate = rev_growth
            assumptions.append(f"Using historical revenue growth rate of {growth_rate * 100:.1f}% for forecast period")
        else:
            assumptions.append(f"Using default mid-term growth rate of {growth_rate * 100:.1f}%")

        # 4. Resolve WACC (discount rate) dynamically from MacroIndicatorsService
        # Determine currency/markets
        is_brl = request.ticker.endswith(".SA") or financial_data.get("currency") == "BRL"
        country_code = "BR" if is_brl else "US"
        
        # Default fallbacks
        rf = 0.105 if is_brl else 0.045
        erp = 0.06
        self.inflation_rate = 0.045 if is_brl else 0.035
        
        # Load from microservice
        try:
            from providers.macro_client import MacroClient
            macro_client = MacroClient()
            indicators = macro_client.get_indicators(country_code)
            rf = float(indicators["components"]["risk_free_rate_rf"])
            erp = float(indicators["market_risk_premium"])
            self.inflation_rate = float(indicators["components"].get("inflation_yoy", self.inflation_rate))
            assumptions.append(f"Loaded dynamic macro indicators for {country_code} (RF={rf * 100:.2f}%, ERP={erp * 100:.2f}%)")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to fetch dynamic macro indicators for {country_code}, using defaults (RF={rf * 100:.2f}%, ERP={erp * 100:.2f}%): {e}")
            assumptions.append(f"Fallback to default macro indicators for {country_code} (RF={rf * 100:.2f}%, ERP={erp * 100:.2f}%)")
            
        beta = financial_data.get("beta", 1.0)
        if beta <= 0.4 or beta > 3.0:
            beta = 1.0
            
        ke = rf + beta * erp
        
        # Weighted Cost of Capital (WACC) estimation
        equity_weight = 1.0
        debt_weight = 0.0
        if market_cap > 0 or total_debt > 0:
            total_val = market_cap + total_debt
            if total_val > 0:
                equity_weight = market_cap / total_val
                debt_weight = total_debt / total_val
                
        kd = rf + 0.02  # Debt premium of 2.0%
        tax_rate = 0.25
        
        estimated_wacc = (equity_weight * ke) + (debt_weight * kd * (1 - tax_rate))
        # Clamp WACC to reasonable boundaries
        wacc = max(0.06, min(estimated_wacc, 0.15))
        assumptions.append(f"Calculated WACC of {wacc * 100:.2f}% (Beta={beta}, Cost of Equity={ke*100:.1f}%, Cost of Debt={kd*100:.1f}%)")

        # 5. Forecast cash flows (dynamic horizon and growth decay)
        horizon = 5
        if request.adjustment_params and "forecast_horizon" in request.adjustment_params:
            horizon = int(request.adjustment_params["forecast_horizon"])
            assumptions.append(f"Adjusted forecast horizon to {horizon} years")
            
        decay_factor = 1.0
        if request.adjustment_params and "growth_decay" in request.adjustment_params:
            decay_factor = float(request.adjustment_params["growth_decay"])
            assumptions.append(f"Applied growth decay factor of {decay_factor * 100:.1f}% per year")

        forecasted_fcf = []
        discounted_fcf = []
        current_fcf = base_fcf
        current_growth = growth_rate
        for year in range(1, horizon + 1):
            current_fcf = current_fcf * (1 + current_growth)
            forecasted_fcf.append(current_fcf)
            df = current_fcf / ((1 + wacc) ** year)
            discounted_fcf.append(df)
            current_growth = current_growth * decay_factor

        # 6. Terminal Value
        terminal_growth = 0.025
        if request.adjustment_params and "terminal_growth" in request.adjustment_params:
            terminal_growth = float(request.adjustment_params["terminal_growth"])
            assumptions.append(f"Adjusted terminal growth rate to {terminal_growth * 100:.2f}%")
        else:
            assumptions.append(f"Terminal growth rate of {terminal_growth * 100:.1f}%")

        # Post-Calculation Validator: terminal_growth < wacc
        if terminal_growth >= wacc:
            return self.create_diagnostic_result(
                reason_code="TERMINAL_GROWTH_EXCEEDS_WACC",
                explanation=f"Terminal growth rate ({terminal_growth * 100:.2f}%) exceeds or equals the WACC ({wacc * 100:.2f}%).",
                triggering_metrics={"terminal_growth": terminal_growth, "wacc": wacc},
                analytical_implication="The perpetuity growth model requires the discount rate (WACC) to be strictly greater than the terminal growth rate. A terminal growth rate higher than WACC implies an infinite enterprise value, rendering the model invalid.",
                baseline_metrics={
                    "free_cash_flow": base_fcf,
                    "terminal_growth": terminal_growth,
                    "wacc": wacc,
                    "shares_outstanding": shares_outstanding
                },
                assumptions=assumptions
            )

        tv = forecasted_fcf[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
        discounted_tv = tv / ((1 + wacc) ** horizon)
        
        # 7. Enterprise Value and Equity Value
        enterprise_value = sum(discounted_fcf) + discounted_tv
        equity_value = enterprise_value - total_debt + total_cash
        
        if equity_value <= 0:
            return self.create_diagnostic_result(
                reason_code="NEGATIVE_EQUITY_VALUE",
                explanation=f"Computed equity value ({equity_value:,.0f}) is negative or zero after subtracting total debt ({total_debt:,.0f}) from enterprise value ({enterprise_value:,.0f}).",
                triggering_metrics={
                    "enterprise_value": enterprise_value,
                    "total_debt": total_debt,
                    "total_cash": total_cash
                },
                analytical_implication="The company's debt burden is larger than the projected present value of its future free cash flows, leaving no residual value for equity holders under this model.",
                baseline_metrics={
                    "enterprise_value": enterprise_value,
                    "total_debt": total_debt,
                    "total_cash": total_cash,
                    "shares_outstanding": shares_outstanding
                },
                assumptions=assumptions
            )
            
        # 8. Intrinsic Value per share
        intrinsic_value = equity_value / shares_outstanding

        # Post-Calculation Validator: simple perpetuity check
        simple_perpetuity_ev = base_fcf / (wacc - terminal_growth)
        simple_perpetuity_equity = simple_perpetuity_ev - total_debt + total_cash
        simple_perpetuity_per_share = simple_perpetuity_equity / shares_outstanding
        
        consistency_warning = None
        if intrinsic_value < simple_perpetuity_per_share * 0.6:
            consistency_warning = "DCFConsistencyWarning: Intrinsic value is significantly below simple perpetuity baseline (less than 60%)."
            assumptions.append("WARNING: Valuation model result is significantly below simple perpetuity baseline")
            
        # Format baseline metrics
        baseline_metrics = {
            "current_price": current_price,
            "market_cap": market_cap,
            "total_revenue": revenue,
            "free_cash_flow": fcf,
            "operating_cash_flow": ocf,
            "shares_outstanding": shares_outstanding,
            "total_debt": total_debt,
            "total_cash": total_cash,
            "wacc": wacc,
            "growth_rate": growth_rate,
            "inflation_rate": self.inflation_rate,
        }
        
        # Structure peer companies from input list
        peer_companies = []
        for idx, peer_raw in enumerate(peers):
            from core.schemas import PeerCompany
            peer_companies.append(PeerCompany(
                ticker=peer_raw.get("ticker", f"PEER{idx}"),
                market_cap=peer_raw.get("market_cap", 0.0),
                multiples=peer_raw.get("multiples", {})
            ))

        return ValuationResult(
            intrinsic_value=round(intrinsic_value, 2),
            methodology_name=self.name,
            assumptions=assumptions,
            baseline_metrics=baseline_metrics,
            peer_comparison=peer_companies,
            fallback_applied=fallback_applied,
            metadata={
                "wacc": wacc,
                "growth_rate": growth_rate,
                "terminal_growth": terminal_growth,
                "enterprise_value": enterprise_value,
                "equity_value": equity_value,
                "wacc_sensitivity_range": request.adjustment_params.get("wacc_sensitivity_range", 0.02) if request.adjustment_params else 0.02,
                "consistency_warning": consistency_warning
            }
        )
