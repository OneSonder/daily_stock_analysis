import logging
import threading
from typing import Any, List

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse

logger = logging.getLogger(__name__)


class HSIScanCommand(BotCommand):
    """HSI signal scan command — scan Hang Seng Index constituents for S1/S2 breakout signals."""

    @property
    def name(self) -> str:
        return "hsi"

    @property
    def aliases(self) -> List[str]:
        return ["hsi", "恒指", "港股扫描", "恒指扫描"]

    @property
    def description(self) -> str:
        return "扫描恒生指数成分股 S1/S2 突破信号"

    @property
    def usage(self) -> str:
        return "/hsi [conditions] — 例如 /hsi s1_breakout,s2_breakout"

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        conditions = args[0] if args else "s1_breakout,s2_breakout"

        thread = threading.Thread(
            target=self._run_scan,
            args=(message, conditions),
            daemon=True,
        )
        thread.start()
        return BotResponse.markdown_response(f"HSI 信号扫描已开始（条件: {conditions}），结果稍后推送...")

    def _run_scan(self, message: BotMessage, conditions: str) -> None:
        try:
            from src.services.hsi_scanner import scan_hsi, format_scan_report

            payload = scan_hsi(period='1y', conditions=conditions, max_workers=8)
            report = format_scan_report(payload)

            from src.notification import NotificationService

            notifier = NotificationService(source_message=message)
            if notifier.is_available():
                notifier.send(report, route_type="report")
                logger.info("HSI scan results sent via bot notification")
        except Exception as e:
            logger.exception("HSI scan bot command failed: %s", e)
