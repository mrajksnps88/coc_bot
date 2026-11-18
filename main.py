"""Clash of Clans Educational Bot — Main Entry Point"""
import argparse
import sys
import logging
from pathlib import Path

from coc_bot.utils.logger import setup_logger
from coc_bot.config.settings import BotSettings
from coc_bot.config import load_config
from coc_bot.core.bot import Bot

def start_bot(args):
    logger = setup_logger("coc_bot", args.log_level)
    
    # Load config file
    config_data = load_config(args.config)
    
    settings = BotSettings(dry_run=args.dry_run, debug_screenshots=args.debug)
    settings.log_level = args.log_level
    settings.screen_regions = config_data.get('screen_regions', {})
    
    farming_cfg = config_data.get('farming', {})
    if farming_cfg:
        for k, v in farming_cfg.items():
            if hasattr(settings.farming, k):
                setattr(settings.farming, k, v)
                
    auto_wall_cfg = config_data.get('auto_wall', {})
    if auto_wall_cfg:
        for k, v in auto_wall_cfg.items():
            if hasattr(settings.auto_wall, k):
                setattr(settings.auto_wall, k, v)
    
    bot = Bot(settings=settings)
    try:
        bot.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Shutting down...")
        bot.stop()
        sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="CoC Educational Bot")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, don't tap")
    parser.add_argument("--debug", action="store_true", help="Save debug screenshots")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG","INFO","WARNING","ERROR"])
    parser.add_argument("--config", type=str, default="coc_bot/config/game_config.yaml")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    subparsers.add_parser("run", help="Start the bot")
    subparsers.add_parser("capture", help="Launch template capture tool")
    subparsers.add_parser("regions", help="Launch region selector tool")
    subparsers.add_parser("test-adb", help="Test ADB connection")
    subparsers.add_parser("screenshot", help="Take a single screenshot")
    
    args = parser.parse_args()
    
    if args.command == "run":
        start_bot(args)
    elif args.command == "capture":
        from coc_bot.tools.template_capture import main as capture_main
        capture_main()
    elif args.command == "regions":
        from coc_bot.tools.region_selector import main as region_main
        region_main()
    elif args.command == "test-adb":
        from coc_bot.utils.adb_utils import test_connection
        test_connection()
    elif args.command == "screenshot":
        print("Not implemented yet.")

if __name__ == "__main__":
    main()
