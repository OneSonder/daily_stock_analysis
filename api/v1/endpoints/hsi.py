import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.services.hsi_scanner import (
    HSI_STOCKS,
    parse_conditions,
    scan_hsi,
    format_scan_report,
    is_hk_market_open,
    VALID_CONDITIONS,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/hsi/scan", summary="HSI signal scan")
async def hsi_scan(
    period: str = Query("1y", description="History period (5d, 1mo, 3mo, 6mo, 1y, 2y, 5y)"),
    conditions: str = Query("s1_breakout,s2_breakout", description="Comma-separated conditions"),
    max_workers: int = Query(8, ge=1, le=16, description="Max parallel workers"),
    check_trading_day: bool = Query(True, description="Skip if HK market closed"),
    output: str = Query("json", description="Output format: json, markdown"),
    enrich: bool = Query(
        False,
        description="When true, enrich matches with quote + news + lite LLM dashboard",
    ),
    top_n: Optional[int] = Query(
        None,
        ge=0,
        le=100,
        description="Match enrich cap when enrich=true: omit/all = all matches; 0 = none; positive = top-N",
    ),
    etnet_top_n: int = Query(
        10,
        ge=0,
        le=100,
        description="ET Net enrich extras when enrich=true: 0 = none; positive = top-N extras (default 10)",
    ),
) -> dict:
    try:
        parse_conditions(conditions)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if enrich:
        from src.services.hsi_enrichment import run_hsi_scan_enriched

        result = run_hsi_scan_enriched(
            period=period,
            conditions=conditions,
            max_workers=max_workers,
            check_trading_day=check_trading_day,
            use_multi_source=False,
            top_n=top_n,
            etnet_top_n=etnet_top_n,
            save_report=True,
        )
        payload = result["payload"]
        if output == "markdown":
            return {
                "report": result["report_text"],
                "report_path": result.get("report_path"),
                "matches": payload.get("matches") or [],
                "top_n": result.get("top_n"),
                "etnet_top_n": result.get("etnet_top_n"),
            }
        return {
            **payload,
            "report": result["report_text"],
            "report_path": result.get("report_path"),
            "top_n": result.get("top_n"),
            "etnet_top_n": result.get("etnet_top_n"),
            "enriched_count": len(result.get("enrichments") or []),
        }

    if check_trading_day and not is_hk_market_open():
        return {
            "skipped": True,
            "skip_reason": "HK market closed today",
            "stats": {"tickers": len(HSI_STOCKS), "total_ms": 0},
        }

    payload = scan_hsi(
        period=period,
        conditions=conditions,
        max_workers=max_workers,
        check_trading_day=check_trading_day,
    )

    if output == "markdown":
        return {"report": format_scan_report(payload), "matches": payload["matches"]}

    return payload


@router.get("/hsi/stocks", summary="List HSI constituent stocks")
async def hsi_stocks():
    return {"count": len(HSI_STOCKS), "stocks": HSI_STOCKS}


@router.get("/hsi/conditions", summary="List valid signal conditions")
async def hsi_conditions():
    return {
        "valid_conditions": sorted(VALID_CONDITIONS),
        "descriptions": {
            "close_vs_entry": "Close >= 20-day high (S1 entry level)",
            "close_vs_s2_entry": "Close >= 55-day high (S2 entry level)",
            "s1_breakout": "Today's high > yesterday's 20-day high",
            "s2_breakout": "Today's high > yesterday's 55-day high",
            "s1_exit": "Today's low < yesterday's 10-day low",
            "s2_exit": "Today's low < yesterday's 20-day low",
        },
    }
